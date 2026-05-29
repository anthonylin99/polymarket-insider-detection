const fs = require("fs");
const path = require("path");
const {
  AlignmentType,
  BorderStyle,
  Document,
  HeadingLevel,
  ImageRun,
  LevelFormat,
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
    font: opts.font || "Arial",
    size: opts.size || 19,
    bold: opts.bold || false,
    italics: opts.italics || false,
    color: opts.color || colors.ink,
    break: opts.break || 0,
  });
}

function para(children, opts = {}) {
  return new Paragraph({
    children: Array.isArray(children) ? children : [text(children)],
    spacing: { before: opts.before || 0, after: opts.after ?? 90, line: opts.line || 252 },
    alignment: opts.alignment,
  });
}

function bullet(children, opts = {}) {
  return new Paragraph({
    children: Array.isArray(children) ? children : [text(children)],
    numbering: { reference: "bul", level: 0 },
    spacing: { before: opts.before || 0, after: opts.after ?? 120, line: 256 },
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

function imageParagraph(filename, width = 340, height = 141) {
  return new Paragraph({
    children: [
      new ImageRun({
        data: fs.readFileSync(path.join(CHARTS, filename)),
        type: "png",
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
    ["allyourmonies_bts_entry.png", "scottynooo_grammys_entry.png"],
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
              margins: { top: 60, bottom: 70, left: 20, right: 20 },
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
  ["Information access point", "Market outcome depends on data a small group may see early.", "Spotify ranks, album sales, awards voting."],
  ["Price still had downside", "Entries were not 99-cent cleanup trades.", "Selected positions averaged 40.9c to 71.6c."],
  ["Wallet behavior stood out", "The trade pattern was unusual for the wallet or market complex.", "Bets 100x to 330x a wallet's usual trade size, plus a paired Spotify view."],
];

const candidateRows = [
  [
    [
      text("Kevindoto", { bold: true }),
      text("0xcd71fd5370880f3d92bb", { break: 1, size: 15, font: "Courier New" }),
      text("941e628c05840fe0d127", { break: 1, size: 15, font: "Courier New" }),
    ],
    "Spotify third-place artist: Weeknd YES / Drake NO",
    "$16.1k total at 43.8c weighted average",
    "~1-2 days before close",
  ],
  [
    [
      text("AllYourMoniesAreBelongToMe", { bold: true }),
      text("0x8564848285e54c65f6cc", { break: 1, size: 15, font: "Courier New" }),
      text("2e3930b49362fbd84b2e", { break: 1, size: 15, font: "Courier New" }),
    ],
    "BTS \"Arirang\" debut-week sales below 3m",
    "$5.7k YES at 71.6c average",
    "42-49 days before close",
  ],
  [
    [
      text("ScottyNooo", { bold: true }),
      text("0xbacd00c9080a82ded56f", { break: 1, size: 15, font: "Courier New" }),
      text("504ee8810af732b0ab35", { break: 1, size: 15, font: "Courier New" }),
    ],
    "Lady Gaga to win 3 Grammys — bought NO",
    "$9.2k NO at 43.2c average",
    "~4 days before close",
  ],
];

const rankRows = [
  ["1", "Kevindoto", "Music streaming rank", "71", "Yes"],
  ["2", "ScottyNooo", "Awards", "69", "Yes"],
  ["3", "blank2389473495", "Music streaming rank", "67", "—"],
  ["4", "SaylorMoon", "Music streaming rank", "53", "—"],
  ["5", "AllYourMoniesAreBelongToMe", "Entertainment release", "52", "Yes"],
  ["6", "BeN", "Music streaming rank", "51", "—"],
];

const movementRows = [
  ["Weeknd #3", "45.3c", "11.2c", "YES"],
  ["Drake not #3", "40.9c", "11.0c", "NO"],
  ["BTS sales <3m", "71.6c", "49.7c", "YES"],
  ["Lady Gaga 3 Grammys", "43.2c", "12.2c", "NO"],
];

const children = [
  h1("Potential Informed Trading on Polymarket"),
  para([text("Anthony Lin", { bold: true }), text(" | Inca Digital Investigations Analyst Take-Home | May 28, 2026")], { after: 140 }),
  para([
    text("Three Polymarket wallets made early, correct, oddly specific bets in entertainment markets where a small group could have known the result first. All three are worth attributing."),
  ]),

  h2("Task 1 · Data Collection"),
  para("I pulled public Polymarket data end to end: market discovery, every trade in the reviewed markets, wallet activity for wash filtering, and a fresh trade-API pull on the four finalist contracts. The reviewed set is 154 resolved markets, $211.9 million in lifetime volume, 205,362 trades, and 44,607 wallets, all in entertainment and attention markets where one side can know first."),

  h2("Task 2 · Heuristics"),
  para("An explainable screen, not a score you have to trust. A strict pass ranks the full wallet universe; a wider pass surfaces rows for manual review. Three tests do the work."),
  table(["Heuristic", "What it tests", "How it showed up"], heuristicsRows, [2500, 3900, contentWidth - 6400]),

  h2("Task 3 · Findings: Candidate Detail"),
  para("Reviewing the strongest rows by hand leaves three wallets and four positions."),
  table(["Wallet", "Market", "Position", "Lead time"], candidateRows, [2550, 3550, 2400, contentWidth - 8500]),

  h2("Task 3 · Entry Timing and Contract Movement"),
  para("The shaded band marks each wallet's buying window against the full price path. Every contract moved against the wallet after entry, then settled on the side it bought, so none of these were last-minute sweeps."),
  chartGrid(),
  table(["Market", "Entry avg.", "Worst after entry", "Won side"], movementRows, [3300, 1700, 2100, contentWidth - 7100]),

  h2("Interpretation"),
  para("The throughline is the market, not the trader. Each bet rests on a public guess about something a small group already had in hand: a year-end streaming rank, a first-week sales number, an awards result the people who vote on it can sense before the show."),
  bullet([
    text("Kevindoto ", { bold: true }),
    text("bought The Weeknd YES and Drake NO in the same year-end ranking, $16.1k at 43.8c blended, and held from a dip to 11c through resolution. Betting both legs means knowing the order of finish, not one artist, which narrows the source to a full-ranking vantage point like a platform or label seat, not a tip about a single name."),
  ]),
  bullet([
    text("AllYourMonies ", { bold: true }),
    text("staked $5.7k on BTS first-week sales landing under 3 million, about 116 times its own median trade. It does not bet that sales look soft; it names a number. A hard threshold called weeks early reads like someone who saw a real sales figure, the kind an insider might know ahead of public announcements."),
  ]),
  bullet([
    text("ScottyNooo ", { bold: true }),
    text("normally trades about $27. It put $9.2k on Lady Gaga not winning three Grammys, roughly 330 times its own median, at 43c and against the market's lean, four days before the night resolved that way. A wallet sizing up that hard on the less-likely side is the behavioral tell. Awards leak through the people who decide them, voters, academy staff, publicists, and betting a specific count rather than a plain win is a finer read than the public had. The contract swung to 12c before settling NO."),
  ]),
  para([
    text("All three paid up into resolution and broke entries into many small fills. That is what you do when you think the answer is fixed and you want size without moving the tape. Paying 90c for a contract you expect to settle at 100c is not careless; it is collecting a near-riskless spread."),
  ], { before: 40 }),
  note([
    text("For an investigations team, the names matter less than the signature they share: small in dollars, large for the wallet, early, priced well below certainty, in a market with a nameable information owner. That is a rule you can run continuously, and every hit is a starting point for attribution, from funding-source clustering to timing the position against when the private number actually existed."),
  ]),
  para([
    text("The caveat I would not bury: public data cannot prove intent. A sharp trader reads public signals well, and Kevindoto is a high-volume, profitable wallet that may simply be a good trader."),
  ]),

  h2("Task 4 · Ranking and Methodology"),
  para("The ranking is a transparent point score, not a black box, applied to every qualifying wallet-market position and built from the same heuristics."),
  bullet([
    text("Conviction ", { bold: true }),
    text("— correct-side notional plus the payoff at stake. This is the bulk of the score."),
  ]),
  bullet([
    text("Non-obvious entry price ", { bold: true }),
    text("— full credit below 60c, partial to 75c, nothing for near-certain buys."),
  ]),
  bullet([
    text("Lead time ", { bold: true }),
    text("— more weight for entries a week or more before resolution."),
  ]),
  bullet([
    text("Clean history ", { bold: true }),
    text("— a bonus when the wallet's wash-trade share is low."),
  ]),
  bullet([
    text("Wallet-relative size ", { bold: true }),
    text("— a jump of 50x or more over the wallet's own median trade."),
  ]),
  bullet([
    text("Public-data control penalty ", { bold: true }),
    text("— Google-trend markets are demoted and pulled out of the insider queue, since public search data explains the edge."),
  ]),
  para("Ranked on merit with controls removed, the top of the queue is:", { before: 40 }),
  table(["#", "Wallet", "Market type", "Score", "In report"], rankRows, [650, 3300, 3100, 1000, contentWidth - 8050]),
  para([
    text("The three profiled here, Kevindoto, ScottyNooo, and AllYourMonies, sit at ranks 1, 2, and 5. The queue holds more, a music-rank wallet at #3 and others below, left as live follow-ups. One pattern outlasts any single name: Kevindoto, blank2389473495, and BeN all bought into the same Weeknd and Drake Spotify-rank markets, a cluster that warrants a coordination check on its own."),
  ], { before: 60 }),

  para([
    text("Support package: ", { bold: true }),
    text("code and CSV artifacts, the reviewed market set, the ranked candidate lead queue, contract-movement outputs, and chart images, available on request rather than as the full working repository."),
  ], { before: 120, after: 0 }),
];

const doc = new Document({
  numbering: {
    config: [
      {
        reference: "bul",
        levels: [
          {
            level: 0,
            format: LevelFormat.BULLET,
            text: "•",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 460, hanging: 240 } } },
          },
        ],
      },
    ],
  },
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
