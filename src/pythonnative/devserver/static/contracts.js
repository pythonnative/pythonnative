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
    case "array": return Array.isArray(value) && (schema.prefixItems
      ? value.length === schema.prefixItems.length && value.every((item, index) => matches(item, schema.prefixItems[index]))
      : value.every(item => matches(item, schema.items || {})));
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
    return matches(value, schema.props[key]);
  });
}
export function validateRemoval(spec, name, changed, removed) {
  const schema = spec.components[name];
  return !!schema && Array.isArray(removed) && new Set(removed).size === removed.length &&
    removed.every(key => typeof key === "string" && Object.hasOwn(schema.props, key) &&
      !schema.required.includes(key) && !Object.hasOwn(changed, key));
}
export function normalize(spec, name, changed, removed = []) {
  const defaults = spec.components[name]?.defaults || {};
  const result = {...changed};
  for (const key of removed) result[key] = defaults[key] ?? null;
  return result;
}
export function requiresRecreation(spec, name, changed, removed = []) {
  const schema = spec.components[name];
  return [...Object.keys(changed), ...removed].some(key => schema?.props[key]?.native?.recreate);
}
export function validateCommand(spec, name, command, args) {
  const contract = spec.components[name]?.commands[command];
  return !!contract && matches(args, {type: "object", properties: contract.arguments,
    required: contract.required || Object.keys(contract.arguments), additionalProperties: false});
}
