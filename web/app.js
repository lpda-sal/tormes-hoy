import { clearDataCache, loadData } from "./data.js";
import { loadStrings, t } from "./i18n.js";

const routes = {
  "/": () => import("./views/home.js"),
  "/weather": () => import("./views/weather.js"),
  "/weather/days": async () => {
    const view = await import("./views/weather.js");
    return { render: view.renderDays };
  },
  "/uv": () => import("./views/uv.js"),
  "/river": () => import("./views/river.js"),
  "/sun": async () => {
    const view = await import("./views/home.js");
    return { render: view.renderSun };
  },
  "/csck": async () => {
    const view = await import("./views/home.js");
    return { render: view.renderCsck };
  },
};

async function renderIdentity() {
  try {
    const summary = await loadData("summary");
    document.title = summary.app?.name ?? document.title;
    document.getElementById("brand").textContent = summary.app?.short_name ?? "";
    document.getElementById("place").textContent = summary.location?.name ?? "";
  } catch {}
}

async function render() {
  const path = location.hash.replace(/^#/, "") || "/";
  const root = document.getElementById("app");
  document.body.classList.toggle("home-screen", path === "/");
  document.getElementById("sun-times").hidden = true;
  root.innerHTML = `<p class="muted">${t("loading")}</p>`;
  try {
    const view = await (routes[path] ?? routes["/"])();
    await view.render(root);
  } catch (error) {
    console.error(error);
    root.innerHTML = `<p class="card notice">${t("load_error")}</p>`;
  }
  renderIdentity();
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
