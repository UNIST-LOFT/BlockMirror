// skulpt-loader.js
export async function loadSkulpt() {
    if (!window.Sk) {
      await Promise.all([
        import("./lib/skulpt.min.js"),
        import("./lib/skulpt-stdlib.js")
      ]);
    }
    return window.Sk;
  }