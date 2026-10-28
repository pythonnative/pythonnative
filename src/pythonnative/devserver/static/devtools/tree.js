// Pure helpers for the Components panel's tree: which nodes show, in what
// order and depth, and how to find a node's visible ancestors. Kept free
// of the DOM so the browser tests can check them directly.
//
// A tree node (from the agent's `tree` request) is
// `{id, name, kind, children, key?, tag?, source?, framework?, text?, error?}`
// where `kind` is "component", "native", "provider", "boundary",
// "suspense", or "fragment".

/** Whether a node is hidden (its children take its place) under `showFramework`. */
export function isHidden(node, showFramework) {
  if (showFramework) return false;
  return !!node.framework || node.kind === "fragment";
}

/** Whether a node matches a lower-cased search query. */
export function matchesQuery(node, query) {
  if (!query) return false;
  return (
    String(node.name || "").toLowerCase().includes(query) ||
    (node.text != null && String(node.text).toLowerCase().includes(query)) ||
    (node.key != null && String(node.key).toLowerCase().includes(query))
  );
}

/**
 * The visible forest under a node list: hidden nodes are replaced by their
 * visible descendants (hoisted to the hidden node's depth).
 *
 * @returns {Array<{node, children}>}
 */
export function visibleForest(nodes, showFramework) {
  const out = [];
  for (const node of nodes || []) {
    if (!node) continue;
    const children = visibleForest(node.children, showFramework);
    if (isHidden(node, showFramework)) out.push(...children);
    else out.push({ node, children });
  }
  return out;
}

/**
 * Flatten the screens' trees into display rows.
 *
 * @param screens `[{screen, root}]` from the `tree` request.
 * @param options.showFramework Show framework components and fragments.
 * @param options.query Search text; rows that match, and their ancestors,
 *   are shown (expanded), and everything else is dropped.
 * @param options.collapsed Set of node ids whose children are hidden
 *   (ignored while searching).
 * @returns {{rows: Array, matches: number, parents: Map<number, number|null>}}
 *   Each row is `{type: "screen", screen}` or `{type: "node", node, id,
 *   depth, hasChildren, expanded, match}`; `parents` maps a visible node id
 *   to its visible parent's id.
 */
export function flattenTree(screens, { showFramework = false, query = "", collapsed = new Set() } = {}) {
  const q = String(query || "").trim().toLowerCase();
  const rows = [];
  const parents = new Map();
  let matches = 0;

  // With a query, keep only matches and their ancestors.
  const prune = (forest) => {
    const kept = [];
    for (const entry of forest) {
      const children = prune(entry.children);
      const match = matchesQuery(entry.node, q);
      if (match) matches += 1;
      if (match || children.length) kept.push({ node: entry.node, children, match });
    }
    return kept;
  };

  const walk = (forest, depth, parentId) => {
    for (const entry of forest) {
      const id = entry.node.id;
      parents.set(id, parentId);
      const hasChildren = entry.children.length > 0;
      const expanded = hasChildren && (q ? true : !collapsed.has(id));
      rows.push({ type: "node", node: entry.node, id, depth, hasChildren, expanded, match: !!entry.match });
      if (expanded) walk(entry.children, depth + 1, id);
      else if (hasChildren) recordParents(entry.children, id, parents);
    }
  };

  for (const screen of screens || []) {
    if (!screen || !screen.root) continue;
    let forest = visibleForest([screen.root], showFramework);
    if (q) forest = prune(forest);
    if (q && !forest.length) continue;
    rows.push({ type: "screen", screen: String(screen.screen || "screen") });
    walk(forest, 0, null);
  }
  return { rows, matches, parents };
}

function recordParents(forest, parentId, parents) {
  for (const entry of forest) {
    parents.set(entry.node.id, parentId);
    recordParents(entry.children, entry.node.id, parents);
  }
}

/**
 * The raw path (root first) from a screen root to node `id`, or `null`.
 */
export function pathTo(screens, id) {
  const search = (node, trail) => {
    if (!node) return null;
    const next = [...trail, node];
    if (node.id === id) return next;
    for (const child of node.children || []) {
      const found = search(child, next);
      if (found) return found;
    }
    return null;
  };
  for (const screen of screens || []) {
    const found = search(screen?.root, []);
    if (found) return found;
  }
  return null;
}

/**
 * Where to put the selection for node `id` given what's visible: the node
 * itself, else (for a hidden framework node) `fallbackId`, else the nearest
 * visible ancestor. Returns `{id, ancestors}` (ancestors are the visible
 * ids to expand, root first) or `null` when the node isn't mounted.
 */
export function revealTarget(screens, id, { showFramework = false, fallbackId = null } = {}) {
  let path = pathTo(screens, id);
  if (path && isHidden(path[path.length - 1], showFramework) && fallbackId != null) {
    const fallback = pathTo(screens, fallbackId);
    if (fallback) path = fallback;
  }
  if (!path) return null;
  const visible = path.filter((node) => !isHidden(node, showFramework));
  if (!visible.length) return null;
  const target = visible[visible.length - 1];
  return { id: target.id, ancestors: visible.slice(0, -1).map((node) => node.id) };
}
