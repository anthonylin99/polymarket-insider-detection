const fs = require("fs");
const path = require("path");
const {
  AlignmentType,
  BorderStyle,
  Document,
  HeadingLevel,
  ImageRun,
  Packer,
  Paragraph,
  ShadingType,
  Table,
  TableCell,
  TableRow,
  TextRun,
  WidthType,
} = require("docx");

const ROOT = path.resolve(__dirname, "..");
const OUT = path.join(ROOT, "report", "Inca_Polymarket_Submission_Memo.docx");
const CHARTS = path.join(ROOT, "report", "charts");

const page = {
  size: { width: 12240, height: 15840 },
  margin: { top: 680, right: 760, bottom: 680, left: 760 },
};
const contentWidth = 12240 - 760 - 760;

const colors = {
  ink: "17201C",
  green: "0F4C3F",
  deep: "102B24",
  pale: "DCEBE5",
  alt: "F4F7F2",
  note: "FFF3E3",
  border: "CBD8D2",
};

const border = { style: BorderStyle.SINGLE, size: 1, color: colors.border };
const borders = { top: border, bottom: border, left: border, right: border };

function text(value, opts = {}) {
  return new TextRun({
    text: value,
    font: "Arial",
    size: opts.size || 19,
    bold: opts.bold || false,
    italics: opts.italics || false,
    color: opts.color || colors.ink,
  });
}

function para(children, opts = {}) {
  return new Paragraph({
    children: Array.isArray(children) ? children : [text(children)],
    spacing: { before: opts.before || 0, after: opts.after ?? 90, line: opts.line || 252 },
    alignment: opts.alignment,
  });
}

function h1(value) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    children: [text(value, { size: 32, bold: true, color: colors.deep })],
    spacing: { before: 0, after: 90 },
  });
}

function h2(value) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    children: [text(value, { size: 23, bold: true, color: colors.green })],
    spacing: { before: 180, after: 70 },
    border: { bottom: { color: "BAD7CE", space: 1, style: BorderStyle.SINGLE, size: 4 } },
  });
}

function cell(children, width, opts = {}) {
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    borders,
    shading: opts.fill ? { fill: opts.fill, type: ShadingType.CLEAR } : undefined,
    margins: { top: 70, bottom: 70, left: 95, right: 95 },
    verticalAlign: "top",
    children: Array.isArray(children) ? children : [para(String(children), { after: 0 })],
  });
}

function table(headers, rows, widths) {
  const header = new TableRow({
    tableHeader: true,
    children: headers.map((h, i) =>
      cell([para([text(h, { bold: true, size: 16, color: colors.deep })], { after: 0, alignment: AlignmentType.CENTER })], widths[i], { fill: colors.pale })
    ),
  });
  const body = rows.map((row, idx) =>
    new TableRow({
      children: row.map((value, i) =>
        cell([para(Array.isArray(value) ? value : String(value), { after: 0 })], widths[i], idx % 2 ? { fill: colors.alt } : {})
      ),
    })
  );
  return new Table({
    width: { size: contentWidth, type: WidthType.DXA },
    columnWidths: widths,
    rows: [header, ...body],
  });
}

function note(value) {
  return new Table({
    width: { size: contentWidth, type: WidthType.DXA },
    columnWidths: [contentWidth],
    rows: [
      new TableRow({
        children: [
          new TableCell({
            width: { size: contentWidth, type: WidthType.DXA },
            borders: {
              top: { style: BorderStyle.NONE },
              bottom: { style: BorderStyle.NONE },
              left: { style: BorderStyle.SINGLE, size: 16, color: "D28B45" },
              right: { style: BorderStyle.NONE },
            },
            shading: { fill: colors.note, type: ShadingType.CLEAR },
            margins: { top: 95, bottom: 95, left: 140, right: 110 },
            children: [para(value, { after: 0 })],
          }),
        ],
      }),
    ],
  });
}

function imageParagraph(filename, width = 315, height = 136) {
  return new Paragraph({
    children: [
      new ImageRun({
        data: fs.readFileSync(path.join(CHARTS, filename)),
        transformation: { width, height },
      }),
    ],
    spacing: { before: 0, after: 0 },
    alignment: AlignmentType.CENTER,
  });
}

function chartGrid() {
  const w = contentWidth / 2;
  const rows = [
    ["kevindoto_weeknd_entry.png", "kevindoto_drake_entry.png"],
    ["allyourmonies_bts_entry.png", "cookiejar_beast_games_entry.png"],
  ];
  return new Table({
    width: { size: contentWidth, type: WidthType.DXA },
    columnWidths: [w, w],
    borders: {
      top: { style: BorderStyle.NONE },
      bottom: { style: BorderStyle.NONE },
      left: { style: BorderStyle.NONE },
      right: { style: BorderStyle.NONE },
      insideHorizontal: { style: BorderStyle.NONE },
      insideVertical: { style: BorderStyle.NONE },
    },
    rows: rows.map(
      (pair) =>
        new TableRow({
          children: pair.map((file) =>
            new TableCell({
              width: { size: w, type: WidthType.DXA },
              margins: { top: 60, bottom: 70, left: 40, right: 40 },
              borders: {
                top: { style: BorderStyle.NONE },
                bottom: { style: BorderStyle.NONE },
                left: { style: BorderStyle.NONE },
                right: { style: BorderStyle.NONE },
              },
              children: [imageParagraph(file)],
            })
          ),
        })
    ),
  });
}

const heuristicsRows = [
  ["Information access point", "Market outcome depends on data a small group may see early.", "Spotify ranks, album sales, production results."],
  ["Price still had downside", "Entries were not 99-cent cleanup trades.", "Selected positions averaged 40.9c to 78.2c."],
  ["Wallet behavior stood out", "The trade pattern was unusual for the wallet or market complex.", "Paired Spotify view, 116x prior median size, early production-result bet."],
];

const candidateRows = [
  [
    "Kevindoto\n0xcd71fd...0d127",
    "Spotify third-place artist: Weeknd YES / Drake NO",
    "$16.1k total at 43.8c weighted average",
    "A paired ranking view that points to platform, label, or distributor data.",
  ],
  [
    "AllYourMoniesAreBelongToMe\n0x856484...84b2e",
    "BTS \"Arirang\" debut-week sales below 3m",
    "$5.7k YES at 71.6c average",
    "A sales-threshold bet far above the wallet's normal trade size.",
  ],
  [
    "cookiejar\n0x614ef9...4f1b",
    "Beast Games contestant 151-175 wins",
    "$5.8k YES at 78.2c average",
    "A production-result market where the answer may have been known before airing.",
  ],
];

const movementRows = [
  ["Weeknd #3", "0.453", "0.112", "0.999", "YES"],
  ["Drake not #3", "0.409", "0.110", "0.999", "NO"],
  ["BTS sales <3m", "0.716", "0.497", "0.999", "YES"],
  ["Beast Games 151-175", "0.782", "0.500", "0.999", "YES"],
];

const taskRows = [
  [
    "1. Data collection",
    "Public Polymarket markets, trades, wallet stats, and refreshed trade API data for selected contracts.",
    "154 markets, 205,362 trades, 44,607 wallets.",
  ],
  [
    "2. Heuristic design",
    "Explainable screen: access point, non-obvious price, wallet behavior, wash/noise filter, contract movement.",
    "No black-box score in the memo.",
  ],
  [
    "3. Application to traders",
    "Screened wallet-market clusters, then manually reviewed the strongest rows.",
    "Three wallets, four positions.",
  ],
  [
    "4. Ranking and methodology",
    "Priority is qualitative and auditable: paired Spotify view, size anomaly, production-access logic.",
    "Support files available on request.",
  ],
];

const children = [
  h1("Potential Informed Trading on Polymarket"),
  para([text("Anthony Lin", { bold: true }), text(" | Inca Digital Investigations Analyst Take-Home | May 28, 2026")]),
  h2("Executive View"),
  para([
    text("I would submit three wallets for follow-up. "),
    text("Kevindoto", { bold: true }),
    text(" is the strongest market-structure case: one wallet bought both sides of the same Spotify ranking thesis, The Weeknd to finish third and Drake not to finish third. "),
    text("AllYourMoniesAreBelongToMe", { bold: true }),
    text(" is the clearest size anomaly: the BTS sales bet was roughly 116 times the wallet's prior median trade. "),
    text("cookiejar", { bold: true }),
    text(" is the cleanest production-access case: it bought a Beast Games outcome weeks before resolution, when the result may already have been known inside the production chain."),
  ]),
  note("The point is not that these wallets simply won. The stronger pattern is correct-side buying in markets where a specific group could plausibly know the answer earlier than the public."),

  h2("Screen and Heuristics"),
  para("The review covered 154 resolved markets, $211.9 million of market lifetime volume, and 205,362 pulled trades. I used a strict ranking screen for the full wallet universe, then a wider triage screen to find candidate rows for manual review."),
  table(["Heuristic", "What it tests", "How it showed up"], heuristicsRows, [2500, 3900, contentWidth - 6400]),

  h2("Candidate Detail"),
  table(["Wallet", "Market", "Position", "Insider-style read"], candidateRows, [2550, 3150, 2300, contentWidth - 8000]),

  h2("Entry Timing and Contract Movement"),
  para("The charts mark each wallet's entry window. In all four markets, the contract later moved against the wallet before closing near 1.00 on the side they bought."),
  chartGrid(),
  table(["Market", "Entry avg.", "Worst after entry", "Last pre-resolution", "Won side"], movementRows, [2700, 1400, 1800, 1900, contentWidth - 7800]),

  h2("Interpretation"),
  para("The $3,000 to $5,000 notional range is not too low for this assignment. A pure whale filter would miss quieter insider-style behavior. The more useful signal is the bundle: knowable-by-few market, non-obvious price, unusual wallet behavior, and price action that later confirms the position."),
  para("Timing depends on the market. A production-result trade can be suspicious weeks before resolution. A streaming-rank trade can cluster closer to resolution if the edge comes from late platform or label data."),

  h2("Submission Methodology Appendix"),
  para("This appendix maps the memo to the four requested tasks so the document can stand on its own without sharing the full GitHub repository."),
  table(["Assignment task", "What I did", "Result"], taskRows, [2200, 5700, contentWidth - 7900]),
  para("If supporting files are requested, send the small artifact package rather than the full working repository. The support package contains the reviewed market set, candidate lead queue, contract movement outputs, chart images, and reproduction scripts.", { after: 0 }),
];

const doc = new Document({
  styles: {
    default: {
      document: { run: { font: "Arial", size: 19, color: colors.ink } },
    },
    paragraphStyles: [
      {
        id: "Heading1",
        name: "Heading 1",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { size: 32, bold: true, font: "Arial", color: colors.deep },
        paragraph: { spacing: { before: 0, after: 90 }, outlineLevel: 0 },
      },
      {
        id: "Heading2",
        name: "Heading 2",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { size: 23, bold: true, font: "Arial", color: colors.green },
        paragraph: { spacing: { before: 180, after: 70 }, outlineLevel: 1 },
      },
    ],
  },
  sections: [{ properties: { page }, children }],
});

Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync(OUT, buffer);
  console.log(OUT);
});
