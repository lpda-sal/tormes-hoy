import { clearDataCache, loadData } from "./data.js";
import { age, esc } from "./format.js";
import { loadStrings, t } from "./i18n.js";

const routes = {
  "/": () => import("./views/home.js"),
  "/weather": () => import("./views/weather.js"),
  "/uv": () => import("./views/uv.js"),
  "/river": () => import("./views/river.js"),
};

async function renderFooter() {
  const footer = document.getElementById("footer");
  try {
    const summary = await loadData("summary");
    document.title = summary.app?.name ?? document.title;
    document.getElementById("brand").textContent = summary.app?.short_name ?? "";
    document.getElementById("place").textContent = summary.location?.name ?? "";
    const offline = navigator.onLine ? "" : ` · ${t("offline")}`;
    footer.innerHTML = `${esc(t("updated", { age: age(summary.generated_at) }))}${esc(offline)}`;
  } catch {
    footer.textContent = "";
  }
}

async function render() {
  const path = location.hash.replace(/^#/, "") || "/";
  const root = document.getElementById("app");
  root.innerHTML = `<p class="muted">${t("loading")}</p>`;
  try {
    const view = await (routes[path] ?? routes["/"])();
    await view.render(root);
  } catch (error) {
    console.error(error);
    root.innerHTML = `<p class="card notice">${t("load_error")}</p>`;
  }
  renderFooter();
  window.scrollTo(0, 0);
}

await loadStrings("es");
window.addEventListener("hashchange", render);
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") {
    clearDataCache();
    render();
  }
});
render();

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("sw.js").catch((e) => console.warn(e));
}
