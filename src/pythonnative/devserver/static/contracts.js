// Portable validation. This module has no DOM dependency, so the same fixtures
// run under Node and against the actual preview renderer in a browser.
export function matches(value, schema) {
  if (schema.anyOf) return schema.anyOf.some(item => matches(value, item));
  if (schema.enum && !schema.enum.some(item => typeof item === typeof value && item === value)) return false;
  switch (schema.type) {
    case "null": return value === null;
    case "string": return typeof value === "string";
    case "boolean": case "event": return typeof value === "boolean";
    case "integer": return Number.isSafeInteger(value);
    case "number": return typeof value === "number" && Number.isFinite(value);
    case "array": return Array.isArray(value) && value.every(item => matches(item, schema.items || {}));
    case "object": {
      if (!value || typeof value !== "object" || Array.isArray(value)) return false;
      if ((schema.required || []).some(key => !Object.hasOwn(value, key))) return false;
      return Object.entries(value).every(([key, item]) => {
        const field = schema.properties?.[key] ?? schema.additionalProperties ?? {};
        return field !== false && matches(item, field === true ? {} : field);
      });
    }
    default: return true;
  }
}
export function validateProps(spec, name, props, partial = false) {
  const schema = spec.components[name];
  if (!schema || !props || typeof props !== "object" || Array.isArray(props)) return false;
  if (!partial && schema.required.some(key => !Object.hasOwn(props, key))) return false;
  return Object.entries(props).every(([key, value]) => {
    if (!Object.hasOwn(schema.props, key)) return false;
    if (schema.props[key].native?.platforms && !schema.props[key].native.platforms.includes("web")) return false;
    if (partial && value === null) return !schema.required.includes(key);
    return matches(value, schema.props[key]);
  });
}
export function normalize(spec, name, changed) {
  const defaults = spec.components[name]?.defaults || {};
  return Object.fromEntries(Object.entries(changed).map(([key, value]) => [key, value === null ? defaults[key] ?? null : value]));
}
export function requiresRecreation(spec, name, changed) {
  const schema = spec.components[name];
  return Object.entries(changed).some(([key, value]) => schema?.props[key]?.native?.recreate ||
    (value === null && schema?.defaults[key] == null));
}
export function validateCommand(spec, name, command, args) {
  const contract = spec.components[name]?.commands[command];
  return !!contract && matches(args, {type: "object", properties: contract.arguments,
    required: contract.required || Object.keys(contract.arguments), additionalProperties: false});
}
