(() => {
  "use strict";

  const source = document.querySelector("#theme-preview-data");
  const grid = document.querySelector("#theme-preview-grid");
  if (!source || !grid) return;

  let themeTypes = JSON.parse(source.textContent);
  if (typeof themeTypes === "string") themeTypes = JSON.parse(themeTypes);
  const states = ["normal", "hover", "pressed", "disabled"];

  function color(value, fallback = "transparent") {
    const match = /^Color\(([^)]+)\)$/.exec(value || "");
    if (!match) return fallback;
    const channels = match[1].split(",").map(Number);
    return `rgb(${channels.slice(0, 3).map((n) => n * 255).join(" ")} / ${channels[3] ?? 1})`;
  }

  function styleBoxStyle(style) {
    const props = style?.properties || {};
    return [
      `background:${color(props.bg_color)}`,
      `border-style:solid`,
      `border-color:${color(props.border_color)}`,
      `border-width:${props.border_width_top || 0}px ${props.border_width_right || 0}px ${props.border_width_bottom || 0}px ${props.border_width_left || 0}px`,
      `border-radius:${props.corner_radius_top_left || 0}px ${props.corner_radius_top_right || 0}px ${props.corner_radius_bottom_right || 0}px ${props.corner_radius_bottom_left || 0}px`,
      `padding:${props.content_margin_top || 8}px ${props.content_margin_right || 8}px ${props.content_margin_bottom || 8}px ${props.content_margin_left || 8}px`,
    ].join(";");
  }

  function previewElement(name, definition, state) {
    const baseType = definition.base_type || name;
    const isButton = baseType.includes("Button") || name.includes("Button") || name === "Button";
    const isPanel = baseType.includes("Panel") || name.includes("Panel");
    const tag = isButton ? "button" : isPanel ? "div" : "span";
    const element = document.createElement(tag);
    element.className = `godot-control godot-${isButton ? "button" : isPanel ? "panel" : "label"}`;
    element.textContent = isPanel ? `${name} content` : name;
    if (tag === "button") {
      element.type = "button";
      element.disabled = state === "disabled";
    }

    const style = definition.styles?.[state] || definition.styles?.normal || definition.styles?.panel;
    element.style.cssText = styleBoxStyle(style);
    const stateSuffix = state === "normal" ? "" : `_${state}`;
    element.style.color = color(
      definition.colors?.[`font${stateSuffix}_color`] || definition.colors?.font_color,
      "#24231f",
    );
    if (definition.font_sizes?.font_size) {
      element.style.fontSize = `${definition.font_sizes.font_size}px`;
    }
    return element;
  }

  for (const [name, definition] of Object.entries(themeTypes)) {
    const card = document.createElement("article");
    card.className = "theme-component-card";
    const heading = document.createElement("header");
    const title = document.createElement("h3");
    title.textContent = name;
    const type = document.createElement("code");
    type.textContent = definition.base_type || name;
    heading.append(title, type);
    card.append(heading);

    const hasStates = definition.styles && states.some((state) => definition.styles[state]);
    const previewStates = hasStates ? states.filter((state) => definition.styles[state]) : ["normal"];
    const previews = document.createElement("div");
    previews.className = "theme-component-states";
    for (const state of previewStates) {
      const item = document.createElement("div");
      const label = document.createElement("small");
      label.textContent = state;
      item.append(label, previewElement(name, definition, state));
      previews.append(item);
    }
    card.append(previews);
    grid.append(card);
  }
})();
