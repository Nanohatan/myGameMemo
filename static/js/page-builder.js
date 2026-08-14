(() => {
  "use strict";

  const root = document.getElementById("screen-builder");
  if (!root) return;

  const paletteSource = parseEmbeddedJson("builder-palette");
  const iconSource = parseEmbeddedJson("builder-icons");
  const icons = Array.isArray(iconSource)
    ? iconSource
    : Object.values(iconSource || {}).filter((value) => typeof value === "string");
  const palette = Object.entries(paletteSource)
    .filter(([, value]) => typeof value === "string" && value.startsWith("Color("))
    .map(([name, value]) => ({ name, value, css: godotColor(value) }));

  const canvas = document.getElementById("game-screen");
  const context = canvas.getContext("2d");
  const widthInput = document.getElementById("canvas-width");
  const heightInput = document.getElementById("canvas-height");
  const sizeLabel = document.getElementById("canvas-size-label");
  const editorList = document.getElementById("part-editor-list");
  const imageCache = new Map();

  let parts = [
    part("header", "管理官コアラ / レベル30　スタミナ 120/120", "nav_settings.svg", "Paper", "StrongBorder", 58),
    part("title", "境界層隔離管理施設・第参区域", "facility_isolation.svg", "Background", "Accent", 94),
    part("navigation", "ホーム　　編成　　談話室　　施設・警報中", "nav_home.svg", "Paper", "Accent", 68),
    part("panel", "現在のチーム 2/3\nSHIYO　　NIE　　未選択", "nav_formation.svg", "Card", "Border", 250),
    part("message", "次の指示があるまで待機だ。", "status_exploring.svg", "Bubble", "BubbleBorder", 84),
    part("panel", "デイリーミッション　1/2\n詳細を確認 ▶", "metric_objects.svg", "Paper", "Border", 92),
    part("navigation", "ホーム　　培養棟　　探索　　ショップ　　施設", "nav_home.svg", "Dark", "LightInk", 72),
  ];

  function parseEmbeddedJson(id) {
    let value = JSON.parse(document.getElementById(id).textContent);
    if (typeof value === "string") value = JSON.parse(value);
    return value;
  }

  function part(type, text, iconName, primary, secondary, height) {
    const icon = icons.find((path) => path.endsWith(`/${iconName}`)) || "";
    return { type, text, icon, primary, secondary, height };
  }

  function godotColor(value) {
    const channels = value.match(/[\d.]+/g)?.map(Number) || [0, 0, 0, 1];
    return `rgba(${Math.round(channels[0] * 255)}, ${Math.round(channels[1] * 255)}, ${Math.round(channels[2] * 255)}, ${channels[3] ?? 1})`;
  }

  function paletteColor(name) {
    return palette.find((color) => color.name === name)?.css || "#ffffff";
  }

  function optionMarkup(items, selected, label) {
    return items.map((item) => {
      const value = typeof item === "string" ? item : item.name;
      const text = typeof item === "string" ? item.split("/").pop().replace(/\.(svg|png)$/i, "") : item.name;
      return `<option value="${value}"${value === selected ? " selected" : ""}>${text || label}</option>`;
    }).join("");
  }

  function renderEditors() {
    editorList.replaceChildren();
    parts.forEach((item, index) => {
      const section = document.createElement("section");
      section.className = "part-editor";
      section.dataset.index = index;
      section.innerHTML = `
        <header>
          <strong>パーツ ${index + 1}</strong>
          <span>
            <button type="button" data-action="up" aria-label="上へ" ${index === 0 ? "disabled" : ""}>↑</button>
            <button type="button" data-action="down" aria-label="下へ" ${index === parts.length - 1 ? "disabled" : ""}>↓</button>
            <button type="button" data-action="remove" aria-label="削除">×</button>
          </span>
        </header>
        <div class="part-fields">
          <label>種類
            <select data-field="type">
              ${optionMarkup(["header", "title", "navigation", "panel", "message"], item.type)}
            </select>
          </label>
          <label>高さ
            <input data-field="height" type="number" min="32" max="1200" value="${item.height}">
          </label>
          <label class="part-text-field">文字
            <textarea data-field="text" rows="2"></textarea>
          </label>
          <label>アイコン
            <select data-field="icon">
              <option value="">なし</option>
              ${optionMarkup(icons, item.icon, "なし")}
            </select>
          </label>
          <label>ベース色
            <select data-field="primary">${optionMarkup(palette, item.primary)}</select>
          </label>
          <label>アクセント色
            <select data-field="secondary">${optionMarkup(palette, item.secondary)}</select>
          </label>
        </div>`;
      section.querySelector('[data-field="text"]').value = item.text;
      editorList.append(section);
    });
  }

  function resizeCanvas() {
    canvas.width = clamp(Number(widthInput.value), 240, 2160);
    canvas.height = clamp(Number(heightInput.value), 320, 3840);
    widthInput.value = canvas.width;
    heightInput.value = canvas.height;
    sizeLabel.textContent = `${canvas.width} × ${canvas.height} px`;
    draw();
  }

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, Number.isFinite(value) ? value : min));
  }

  function draw() {
    const scale = canvas.width / 540;
    const background = paletteColor("Background");
    context.clearRect(0, 0, canvas.width, canvas.height);
    context.fillStyle = background;
    context.fillRect(0, 0, canvas.width, canvas.height);

    let y = 0;
    parts.forEach((item) => {
      const height = Math.max(32, item.height) * scale;
      drawPart(item, 0, y, canvas.width, height, scale);
      y += height;
    });

    if (y < canvas.height) {
      context.strokeStyle = paletteColor("Border");
      context.setLineDash([6 * scale, 6 * scale]);
      context.strokeRect(10 * scale, y + 10 * scale, canvas.width - 20 * scale, Math.max(0, canvas.height - y - 20 * scale));
      context.setLineDash([]);
    }
  }

  function drawPart(item, x, y, width, height, scale) {
    const primary = paletteColor(item.primary);
    const secondary = paletteColor(item.secondary);
    const padding = 14 * scale;
    const iconSize = Math.min(28 * scale, height - padding * 1.2);

    context.fillStyle = primary;
    context.fillRect(x, y, width, height);
    context.strokeStyle = secondary;
    context.lineWidth = Math.max(1, 1.5 * scale);

    if (item.type === "message") {
      roundRect(context, x + 6 * scale, y + 8 * scale, width - 12 * scale, height - 16 * scale, 10 * scale);
      context.stroke();
    } else {
      context.beginPath();
      context.moveTo(x, y + height - context.lineWidth / 2);
      context.lineTo(x + width, y + height - context.lineWidth / 2);
      context.stroke();
    }

    const textColor = item.type === "navigation" && item.primary === "Dark"
      ? paletteColor("LightInk")
      : paletteColor("Ink");
    context.fillStyle = textColor;
    const baseFont = item.type === "title" ? 23 : item.type === "header" ? 13 : 16;
    context.font = `${item.type === "title" ? 700 : 600} ${baseFont * scale}px system-ui, sans-serif`;
    context.textBaseline = "middle";

    const iconX = padding;
    const iconY = y + (height - iconSize) / 2;
    if (item.icon) drawIcon(item.icon, iconX, iconY, iconSize);
    const textX = item.icon ? iconX + iconSize + 12 * scale : padding;
    drawWrappedText(item.text, textX, y + height / 2, width - textX - padding, height - padding, 22 * scale);
  }

  function drawWrappedText(text, x, centerY, maxWidth, maxHeight, lineHeight) {
    const paragraphs = String(text).split("\n");
    const lines = [];
    paragraphs.forEach((paragraph) => {
      let line = "";
      Array.from(paragraph).forEach((character) => {
        const candidate = line + character;
        if (line && context.measureText(candidate).width > maxWidth) {
          lines.push(line);
          line = character;
        } else {
          line = candidate;
        }
      });
      lines.push(line);
    });
    const visible = lines.slice(0, Math.max(1, Math.floor(maxHeight / lineHeight)));
    const startY = centerY - ((visible.length - 1) * lineHeight) / 2;
    visible.forEach((line, index) => context.fillText(line, x, startY + index * lineHeight, maxWidth));
  }

  function drawIcon(path, x, y, size) {
    let image = imageCache.get(path);
    if (!image) {
      image = new Image();
      image.onload = draw;
      image.src = `${document.baseURI}${path}`;
      imageCache.set(path, image);
    }
    if (image.complete && image.naturalWidth) context.drawImage(image, x, y, size, size);
  }

  function roundRect(ctx, x, y, width, height, radius) {
    const r = Math.min(radius, width / 2, height / 2);
    ctx.beginPath();
    ctx.roundRect(x, y, width, height, r);
  }

  editorList.addEventListener("input", (event) => {
    const field = event.target.dataset.field;
    if (!field) return;
    const section = event.target.closest(".part-editor");
    const index = Number(section.dataset.index);
    parts[index][field] = field === "height" ? clamp(Number(event.target.value), 32, 1200) : event.target.value;
    draw();
  });

  editorList.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-action]");
    if (!button) return;
    const index = Number(button.closest(".part-editor").dataset.index);
    if (button.dataset.action === "remove") parts.splice(index, 1);
    if (button.dataset.action === "up" && index > 0) [parts[index - 1], parts[index]] = [parts[index], parts[index - 1]];
    if (button.dataset.action === "down" && index < parts.length - 1) [parts[index + 1], parts[index]] = [parts[index], parts[index + 1]];
    renderEditors();
    draw();
  });

  document.getElementById("add-part").addEventListener("click", () => {
    parts.push(part("panel", "新しいパーツ", "", "Paper", "Border", 96));
    renderEditors();
    draw();
    editorList.lastElementChild?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  });

  document.getElementById("download-png").addEventListener("click", () => {
    draw();
    const link = document.createElement("a");
    link.download = `game-screen-${canvas.width}x${canvas.height}.png`;
    link.href = canvas.toDataURL("image/png");
    link.click();
  });

  widthInput.addEventListener("change", resizeCanvas);
  heightInput.addEventListener("change", resizeCanvas);
  renderEditors();
  resizeCanvas();
})();
