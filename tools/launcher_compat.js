// Compatibility fix for the official Launcher JSON-import path. That path
// supplies productInfo without the database-only `product` member; macro save
// otherwise throws before sending a single USB packet. Keep the official
// encoder, transfer, readback validation and UI unchanged.
(() => {
    if (location.origin !== "https://launcher.keychron.com") return "wrong origin";
    if (window.__bat68LauncherCompat) return window.__bat68LauncherCompat;
    const state = window.__bat68LauncherCompat = {status: "waiting", patched: 0};
    function install() {
        const chunks = window.webpackChunkkeyboard;
        if (!chunks) return false;
        let require;
        chunks.push([["bat68-compat-" + Date.now()], {}, r => { require = r; }]);
        if (!require?.m) return false;
        for (const id of Object.keys(require.m)) {
            if (!require.m[id].toString().includes("getMacroWriteBufferSize")) continue;
            const exports = require(id);
            for (const Klass of Object.values(exports)) {
                if (typeof Klass !== "function" || !Klass.Buffer || !Klass.prototype?.setMacro) continue;
                const keyboard = new Klass({vendorId: 0x0c45, productId: 0x8037,
                    productName: "BAT68 QMK HE", opened: false}, null, 12, {}, null);
                const proto = Object.getPrototypeOf(keyboard.baseCommand);
                if (typeof proto.getMacroWriteBufferSize !== "function") continue;
                proto.getMacroWriteBufferSize = function () {
                    const capacity = this.keyboard.constructor.Buffer().length - 4;
                    const desc = this.keyboard.productInfo?.product?.desc;
                    const requested = /^\d+$/.test(desc) ? parseInt(desc, 10) - 4 : 28;
                    return Math.max(1, Math.min(requested, capacity));
                };
                state.patched++;
            }
        }
        if (state.patched) { state.status = "applied"; return true; }
        return false;
    }
    if (!install()) {
        let attempts = 0;
        const timer = setInterval(() => {
            try {
                if (install()) clearInterval(timer);
                else if (++attempts >= 300) {state.status = "unsupported bundle";clearInterval(timer);}
            } catch (error) {state.status = error.message;clearInterval(timer);}
        }, 100);
    }
    return state;
})();
