import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
/* Maré · React — the structural enforcement layer.
 *
 * These primitives ARE the Maré grammar. They expose no `style` or free `className` prop, so there
 * is no ergonomic path to a generic page: you compose the Shore, a headline is sea-blocks, app
 * `state` is a closed union (you cannot write "running"/"idle" — it won't compile). Building
 * correctly is the most logical thing to do because it is the only thing the API offers; deviating
 * means leaving Maré (raw <div>s), which the conformance lint then flags. Render output is the
 * `src/patterns.css` grammar; theming + tokens flow from `dist/mare.css`.
 */
import { useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
/* ── fields: a complete listbox, not a theme-fragile native popup ─────────── */
export function Select({ value, options, onChange, ariaLabel, label, placeholder = "Select", disabled = false, size = "default", }) {
    const id = useId();
    const triggerRef = useRef(null);
    const menuRef = useRef(null);
    const [open, setOpen] = useState(false);
    const selectedIndex = options.findIndex((option) => option.value === value);
    const [activeIndex, setActiveIndex] = useState(Math.max(0, selectedIndex));
    const [menuStyle, setMenuStyle] = useState({});
    const [portalTheme, setPortalTheme] = useState(null);
    const activeValueRef = useRef(undefined);
    const menuCapRef = useRef(null);
    const selected = selectedIndex >= 0 ? options[selectedIndex] : undefined;
    const enabledIndexes = useMemo(() => options.map((option, index) => option.disabled ? -1 : index).filter((index) => index >= 0), [options]);
    /* Interactions track the active OPTION, not its position — a reorder or
       prepend while open must not silently move the active descendant. */
    function setActive(index) {
        activeValueRef.current = options[index]?.value;
        setActiveIndex(index);
    }
    useEffect(() => {
        const tracked = activeValueRef.current;
        const kept = tracked !== undefined ? options.findIndex((option) => option.value === tracked) : -1;
        const next = kept >= 0 ? kept : Math.max(0, options.findIndex((option) => option.value === value));
        activeValueRef.current = options[next]?.value;
        setActiveIndex(next);
    }, [options, value]);
    function updatePosition() {
        const trigger = triggerRef.current;
        if (!trigger)
            return;
        const rect = trigger.getBoundingClientRect();
        const margin = parseFloat(getComputedStyle(trigger).getPropertyValue("--mare-space-2")) || 8;
        const menu = menuRef.current;
        // The stylesheet's row cap, read once per open (before any inline override).
        if (menu && menuCapRef.current === null)
            menuCapRef.current = parseFloat(getComputedStyle(menu).maxHeight) || Infinity;
        const cap = menuCapRef.current ?? Infinity;
        // scrollHeight is content height (stable across passes); the menu never
        // renders taller than its cap, so fit decisions use the capped height.
        const menuHeight = Math.min(menu?.scrollHeight ?? 0, cap);
        const below = window.innerHeight - rect.bottom - margin;
        const above = rect.top - margin;
        const openAbove = menuHeight > below && above > below;
        const available = Math.max(0, openAbove ? above : below);
        setMenuStyle({
            left: rect.left,
            width: rect.width,
            ...(openAbove ? { bottom: window.innerHeight - rect.top } : { top: rect.bottom }),
            // clamp only under the cap — the row cap itself stays with the stylesheet
            // (floored at one row so a cramped viewport degrades to scroll, not to nothing)
            ...(menuHeight > available ? { maxHeight: Math.max(rect.height, available) } : {}),
        });
    }
    useLayoutEffect(() => {
        if (!open)
            return;
        updatePosition();
        const active = menuRef.current?.querySelector(`[data-index="${activeIndex}"]`);
        active?.scrollIntoView({ block: "nearest" });
        // `options` is a dependency so content changes re-measure placement — an
        // appended row must re-clamp or flip, not overflow until a scroll happens.
    }, [open, activeIndex, options]);
    // The portal escapes any local-weather scope — mirror the nearest data-theme
    // onto the menu, and keep it live while open (a toggle can flip mid-open).
    useLayoutEffect(() => {
        if (!open)
            return;
        const scope = triggerRef.current?.closest("[data-theme]") ?? null;
        const read = () => setPortalTheme(scope?.dataset.theme ?? null);
        read();
        if (!scope)
            return;
        const observer = new MutationObserver(read);
        observer.observe(scope, { attributes: true, attributeFilter: ["data-theme"] });
        return () => observer.disconnect();
    }, [open]);
    useEffect(() => {
        if (open)
            return;
        menuCapRef.current = null;
        setMenuStyle({});
    }, [open]);
    // The popup must not outlive its preconditions: an async source draining the
    // options, or the control becoming disabled, closes it rather than leaving a
    // live listbox behind a trigger that can no longer toggle it.
    useEffect(() => {
        if (open && (disabled || !options.length))
            setOpen(false);
    }, [open, options, disabled]);
    useEffect(() => {
        if (!open)
            return;
        const close = (event) => {
            const target = event.target;
            if (!triggerRef.current?.contains(target) && !menuRef.current?.contains(target))
                setOpen(false);
        };
        const reposition = () => updatePosition();
        document.addEventListener("pointerdown", close);
        window.addEventListener("resize", reposition);
        window.addEventListener("scroll", reposition, true);
        return () => {
            document.removeEventListener("pointerdown", close);
            window.removeEventListener("resize", reposition);
            window.removeEventListener("scroll", reposition, true);
        };
    }, [open]);
    function move(direction) {
        if (!enabledIndexes.length)
            return;
        const position = enabledIndexes.indexOf(activeIndex);
        const start = position < 0 ? (direction > 0 ? -1 : 0) : position;
        setActive(enabledIndexes[(start + direction + enabledIndexes.length) % enabledIndexes.length]);
    }
    function choose(index) {
        if (disabled)
            return;
        const option = options[index];
        if (!option || option.disabled)
            return;
        onChange(option.value);
        setActive(index);
        setOpen(false);
        triggerRef.current?.focus();
    }
    function onKeyDown(event) {
        if (event.key === "Tab" && open) {
            setOpen(false);
            return;
        } // let focus move on; the popup must not outlive it
        if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            if (!options.length)
                return;
            if (!open) {
                setActive(selectedIndex >= 0 ? selectedIndex : enabledIndexes[0] ?? 0);
                setOpen(true);
            }
            else
                move(event.key === "ArrowDown" ? 1 : -1);
            return;
        }
        if (event.key === "Home" && open) {
            event.preventDefault();
            setActive(enabledIndexes[0] ?? 0);
            return;
        }
        if (event.key === "End" && open) {
            event.preventDefault();
            setActive(enabledIndexes[enabledIndexes.length - 1] ?? 0);
            return;
        }
        if ((event.key === "Enter" || event.key === " ") && open) {
            event.preventDefault();
            choose(activeIndex);
            return;
        }
        if (event.key === "Escape" && open) {
            event.preventDefault();
            setOpen(false);
            return;
        }
        if (event.key.length === 1 && !event.metaKey && !event.ctrlKey && !event.altKey) {
            const needle = event.key.toLocaleLowerCase();
            const match = options.findIndex((option) => !option.disabled && option.label.toLocaleLowerCase().startsWith(needle));
            if (match >= 0) {
                event.preventDefault();
                setActive(match);
                setOpen(true);
            }
        }
    }
    const control = _jsxs("div", { className: `mare-select${size === "small" ? " mare-select--small" : ""}`, children: [!label ? _jsx("span", { id: `${id}-label`, className: "mare-sr-only", children: ariaLabel }) : null, _jsxs("button", { ref: triggerRef, type: "button", className: "mare-select-trigger", role: "combobox", "aria-labelledby": `${id}-label ${id}-value`, "aria-controls": `${id}-listbox`, "aria-expanded": open, "aria-haspopup": "listbox", "aria-activedescendant": open && options[activeIndex] ? `${id}-option-${activeIndex}` : undefined, disabled: disabled, onClick: () => { if (!open && !options.length)
                    return; setActive(selectedIndex >= 0 ? selectedIndex : enabledIndexes[0] ?? 0); setOpen((current) => !current); }, onKeyDown: onKeyDown, onBlur: (event) => {
                    const next = event.relatedTarget;
                    if (!menuRef.current?.contains(next) && !triggerRef.current?.contains(next))
                        setOpen(false);
                }, children: [_jsx("span", { id: `${id}-value`, className: selected ? undefined : "is-placeholder", children: selected?.label ?? placeholder }), _jsx("svg", { "aria-hidden": "true", viewBox: "0 0 16 16", children: _jsx("path", { d: "m4 6 4 4 4-4" }) })] }), open ? createPortal(_jsx("div", { ref: menuRef, id: `${id}-listbox`, className: "mare-select-menu", role: "listbox", "aria-label": ariaLabel, style: menuStyle, "data-theme": portalTheme ?? undefined, children: options.map((option, index) => _jsxs("button", { type: "button", role: "option", id: `${id}-option-${index}`, "data-index": index, tabIndex: -1, "aria-selected": index === selectedIndex, disabled: option.disabled, className: `mare-select-option${index === activeIndex ? " is-active" : ""}`, onPointerMove: () => !option.disabled && setActive(index), onClick: () => choose(index), children: [_jsxs("span", { children: [_jsx("strong", { children: option.label }), option.description ? _jsx("small", { children: option.description }) : null] }), index === selectedIndex ? _jsx("svg", { "aria-hidden": "true", viewBox: "0 0 16 16", children: _jsx("path", { d: "m3 8 3 3 7-7" }) }) : null] }, option.value)) }), document.body) : null] });
    return label ? _jsxs("div", { className: "field", children: [_jsx("span", { id: `${id}-label`, className: "lbl", children: label }), control] }) : control;
}
/* ── the page is the Shore. arrival = sky/sand/sea; work = the sand alone ────── */
export function Page({ variant, children }) {
    return _jsx("main", { className: `mare-page mare-page--${variant}`, children: children });
}
/* ── sky: the chrome ─────────────────────────────────────────────────────────── */
export function TopBar({ children }) {
    return _jsx("header", { className: "mare-top", children: children });
}
export function Wordmark({ href = "/", children = "maré" }) {
    return (_jsx("a", { className: "mare-wordmark", href: href, "aria-label": typeof children === "string" ? children : "maré", children: children }));
}
export function Nav({ children }) {
    return _jsx("nav", { className: "mare-nav", children: children });
}
export function NavItem({ href, current, children }) {
    return (_jsx("a", { className: "mare-nav-item", href: href, "aria-current": current ? "page" : undefined, children: children }));
}
export function ThemeToggle() {
    function toggle() {
        const root = document.documentElement;
        const next = root.dataset.theme === "night" ? "day" : "night";
        root.dataset.theme = next;
        try {
            localStorage.setItem("mare-theme", next);
        }
        catch {
            /* private mode */
        }
    }
    return (_jsxs("button", { className: "mare-toggle", onClick: toggle, "aria-label": "Day / Night", type: "button", children: [_jsxs("svg", { className: "mare-toggle-sun", width: "17", height: "17", viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "1.7", strokeLinecap: "round", children: [_jsx("circle", { cx: "12", cy: "12", r: "4.2" }), _jsx("path", { d: "M12 2v2M12 20v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M2 12h2M20 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4" })] }), _jsx("svg", { className: "mare-toggle-moon", width: "17", height: "17", viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "1.7", strokeLinecap: "round", strokeLinejoin: "round", children: _jsx("path", { d: "M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8z" }) })] }));
}
/* ── sky/sand seam: the lit headline. words become sea-blocks — not a choice ──── */
export function Hero({ children }) {
    return _jsx("section", { className: "mare-hero", children: children });
}
export function Headline({ words }) {
    return (_jsx("h1", { className: "mare-headline", children: words.map((w, i) => (_jsx("span", { className: "mare-block", children: w }, i))) }));
}
export function Voice({ children }) {
    return _jsx("p", { className: "mare-voice", children: children });
}
/* ── sea: the living horizon. drop it in; src/mark.js draws the stipple ──────── */
export function HorizonMark() {
    return (_jsx("div", { className: "mare-horizon", "aria-hidden": "true", children: _jsx("canvas", { "data-mark": true }) }));
}
/* ── the sea-water pool — the one sanctioned filled body (≤ 1–2 per surface) ──── */
export function Pool({ label, children }) {
    return (_jsx("section", { className: "mare-pool", "aria-label": label, children: children }));
}
/* ── sand: the launcher. `state` is the App-Contract scale, enforced by the type ── */
export function AppList({ children }) {
    return _jsx("ul", { className: "mare-applist", children: children });
}
export function App({ name, purpose, state = "ready", pulse, href = "#", }) {
    return (_jsxs("li", { className: "mare-app", "data-state": state, children: [_jsx("a", { className: "mare-app-name", href: href, children: name }), pulse ? _jsx("span", { className: "mare-app-pulse", children: pulse }) : null, _jsx("span", { className: "mare-app-for", children: purpose }), state !== "ready" ? _jsx("span", { className: "mare-app-state", children: state }) : null] }));
}
/* ── the waterline labels ────────────────────────────────────────────────────── */
export function Foot({ left, right }) {
    return (_jsxs("footer", { className: "mare-foot", children: [_jsx("span", { children: left }), _jsx("span", { children: right })] }));
}
