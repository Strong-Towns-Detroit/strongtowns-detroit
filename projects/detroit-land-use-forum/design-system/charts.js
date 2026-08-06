const NS = "http://www.w3.org/2000/svg";
const C = {
  navy: "#0c2340", blue: "#a7c6ed", blueAccess: "#5790db",
  yellow: "#ffb549", red: "#c83a3a", muted: "#526276",
  paper: "#fffdf8", white: "#ffffff"
};

function el(name, attrs = {}, text = "") {
  const node = document.createElementNS(NS, name);
  Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
  if (text) node.textContent = text;
  return node;
}

function svgFor(target, height, label) {
  const svg = el("svg", {viewBox: `0 0 900 ${height}`, role: "img", "aria-label": label});
  document.querySelector(target).replaceChildren(svg);
  return svg;
}

function text(svg, x, y, value, attrs = {}) {
  svg.append(el("text", {x, y, fill: C.navy, "font-size": 18, ...attrs}, value));
}

function barChart() {
  const data = [
    {label: "5 minutes", value: 24},
    {label: "10 minutes", value: 126},
    {label: "15 minutes", value: 343}
  ];
  const svg = svgFor("#bar-chart", 390, "Reachable area grows from 24 square kilometers at five minutes to 343 at fifteen minutes.");
  const left = 175, right = 70, width = 900 - left - right, max = 360;
  [0, 100, 200, 300].forEach(v => {
    const x = left + width * v / max;
    svg.append(el("line", {x1: x, y1: 24, x2: x, y2: 310, stroke: "#d8dee5", "stroke-width": 1}));
    text(svg, x, 345, `${v} km²`, {"text-anchor": "middle", "font-size": 14, fill: C.muted});
  });
  data.forEach((d, i) => {
    const y = 52 + i * 92;
    const w = width * d.value / max;
    text(svg, left - 18, y + 30, d.label, {"text-anchor": "end", "font-weight": 700, "font-size": 17});
    svg.append(el("rect", {x: left, y, width: w, height: 46, fill: i === 2 ? C.yellow : C.blue}));
    svg.append(el("rect", {x: left, y, width: 8, height: 46, fill: C.navy}));
    text(svg, left + w + 14, y + 31, `${d.value} km²`, {"font-weight": 700, "font-size": 17});
  });
  text(svg, left, 382, "Reachable area", {"font-size": 13, "font-weight": 700, "letter-spacing": 1.5, fill: C.red});
}

function stackChart() {
  const data = [
    {label: "Homes & mixed use", value: 38, color: C.navy},
    {label: "Public realm", value: 22, color: C.blueAccess},
    {label: "Parking", value: 26, color: C.yellow},
    {label: "Other", value: 14, color: "#d8dee5"}
  ];
  const svg = svgFor("#stack-chart", 390, "Illustrative land composition: homes and mixed use 38 percent, public realm 22, parking 26, and other 14.");
  let x = 40;
  const y = 80, totalWidth = 820;
  data.forEach((d, i) => {
    const w = totalWidth * d.value / 100;
    svg.append(el("rect", {x, y, width: w, height: 84, fill: d.color}));
    text(svg, x + w / 2, y + 50, `${d.value}%`, {
      "text-anchor": "middle", "font-size": w < 130 ? 16 : 22, "font-weight": 700,
      fill: i === 0 || i === 1 ? C.white : C.navy
    });
    const labelY = 215 + (i % 2) * 70;
    svg.append(el("line", {x1: x + w / 2, y1: y + 84, x2: x + w / 2, y2: labelY - 25, stroke: d.color, "stroke-width": 3}));
    text(svg, x + w / 2, labelY, d.label, {"text-anchor": "middle", "font-size": 15, "font-weight": 700});
    x += w;
  });
  text(svg, 40, 365, "SHARE OF ILLUSTRATIVE LAND AREA", {"font-size": 13, "font-weight": 700, "letter-spacing": 1.5, fill: C.red});
}

function lineChart() {
  const detroit = [100, 96, 91, 88, 93, 103];
  const context = [100, 102, 104, 106, 108, 111];
  const years = [2000, 2005, 2010, 2015, 2020, 2025];
  const svg = svgFor("#line-chart", 390, "Indexed trend demonstration with Detroit declining then recovering and a comparison increasing gradually.");
  const left = 55, top = 35, width = 690, height = 275;
  const x = i => left + i * width / (years.length - 1);
  const y = v => top + height - (v - 84) / 30 * height;
  [90, 100, 110].forEach(v => {
    svg.append(el("line", {x1: left, y1: y(v), x2: left + width, y2: y(v), stroke: "#496078", "stroke-width": 1}));
    text(svg, left - 12, y(v) + 5, String(v), {"text-anchor": "end", "font-size": 13, fill: C.blue});
  });
  years.forEach((yr, i) => text(svg, x(i), 345, String(yr), {"text-anchor": "middle", "font-size": 13, fill: C.blue}));
  const path = values => values.map((v, i) => `${i ? "L" : "M"} ${x(i)} ${y(v)}`).join(" ");
  svg.append(el("path", {d: path(context), fill: "none", stroke: C.blue, "stroke-width": 4, "stroke-dasharray": "10 8"}));
  svg.append(el("path", {d: path(detroit), fill: "none", stroke: C.yellow, "stroke-width": 7}));
  detroit.forEach((v, i) => svg.append(el("circle", {cx: x(i), cy: y(v), r: 6, fill: C.navy, stroke: C.yellow, "stroke-width": 4})));
  text(svg, 765, y(detroit.at(-1)) + 5, "Focus series", {"font-size": 16, "font-weight": 700, fill: C.yellow});
  text(svg, 765, y(context.at(-1)) + 5, "Context", {"font-size": 16, "font-weight": 700, fill: C.blue});
}

barChart();
stackChart();
lineChart();
