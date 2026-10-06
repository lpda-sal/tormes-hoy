// UI strings live in i18n/<lang>.json; code never contains Spanish text.
let strings = {};

export async function loadStrings(lang = "es") {
  const res = await fetch(`i18n/${lang}.json`);
  strings = await res.json();
}

/** Translate a dotted key, replacing {placeholders} with vars. */
export function t(key, vars = {}) {
  const value = key.split(".").reduce((node, k) => node?.[k], strings);
  if (typeof value !== "string") return key;
  return value.replace(/\{(\w+)\}/g, (_, name) => String(vars[name] ?? ""));
}
