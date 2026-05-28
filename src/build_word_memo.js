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
const CHART = path.join(ROOT, "report", "candidate_market_movements.png");

const page = {
  size: { width: 12240, height: 15840 },
  margin: { top: 720, right: 806, bottom: 720, left: 806 },
};
const contentWidth = 12240 - 806 - 806;

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
    size: opts.size || 20,
    bold: opts.bold || false,
    italics: opts.italics || false,
    color: opts.color || colors.ink,
  });
}

function para(children, opts = {}) {
  return new Paragraph({
    children: Array.isArray(children) ? children : [text(children)],
    spacing: { before: opts.before || 0, after: opts.after || 120, line: opts.line || 276 },
    alignment: opts.alignment,
  });
}

function h1(value) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    children: [text(value, { size: 34, bold: true, color: colors.deep })],
    spacing: { before: 0, after: 120 },
  });
}

function h2(value) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    children: [text(value, { size: 24, bold: true, color: colors.green })],
    spacing: { before: 220, after: 80 },
    border: { bottom: { color: "BAD7CE", space: 1, style: BorderStyle.SINGLE, size: 4 } },
  });
}

function cell(children, width, opts = {}) {
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    borders,
    shading: opts.fill ? { fill: opts.fill, type: ShadingType.CLEAR } : undefined,
    margins: { top: 80, bottom: 80, left: 110, right: 110 },
    verticalAlign: "top",
    children: Array.isArray(children) ? children : [para(String(children), { after: 0 })],
  });
}

function table(headers, rows, widths) {
  const header = new TableRow({
    tableHeader: true,
    children: headers.map((h, i) =>
      cell([para([text(h, { bold: true, size: 17, color: colors.deep })], { after: 0, alignment: AlignmentType.CENTER })], widths[i], { fill: colors.pale })
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
            margins: { top: 110, bottom: 110, left: 160, right: 120 },
            children: [para(value, { after: 0 })],
          }),
        ],
      }),
    ],
  });
}

const heuristicsRows = [
  ["Specific information owner", "The market maps to a real access point.", "Spotify ranking data, album-sales tracking, production-result knowledge."],
  ["Non-obvious entry price", "Buys at 40 to 80 cents still have downside; this excludes near-certain cleanup.", "Selected entries were below 80 cents on average except cookiejar at 78.2 cents."],
  ["Clustered or paired conviction", "Repeated buying or a linked long/short view is stronger than one lucky fill.", "Kevindoto bought The Weeknd YES and Drake NO in the same Spotify rank complex."],
  ["Wallet-relative abnormality", "A smaller trade can matter when it is large for that wallet.", "AllYourMonies' BTS position was about 116 times prior median trade size."],
  ["Contract movement after entry", "A real lead should survive later price volatility and resolve in the predicted direction.", "Each selected contract later traded to 99.9 cents before resolving at 1.00."],
];

const candidateRows = [
  [
    "1",
    "Kevindoto\n0xcd71fd...0d127",
    "Bought $10,520 of The Weeknd YES at 45.3 cents average and $5,549 of Drake NO at 40.9 cents average.",
    "The paired trade is the signal: one wallet expressed both sides of the third-place Spotify ranking question. A plausible source would be platform analytics, label dashboards, distributor data, or unpublished year-end ranking snapshots.",
  ],
  [
    "2",
    "AllYourMoniesAreBelongToMe\n0x856484...84b2e",
    "Bought $5,747 of BTS \"Arirang\" debut-week sales below 3 million at 71.6 cents average, 42 to 49 days before resolution.",
    "Album-sales thresholds are natural information-asymmetry markets. Labels, distributors, chart-reporting vendors, and sales-operations teams can see preorder or tracking signals before the public.",
  ],
  [
    "3",
    "cookiejar\n0x614ef9...4f1b",
    "Bought $5,806 of the Beast Games contestant-number 151-175 YES contract at 78.2 cents average, 38 to 48 days before resolution.",
    "This is the cleanest role-conflict story. If the season was filmed and edited, someone in production, casting, post-production, or the contestant network could know the result long before the public market resolved.",
  ],
];

const movementRows = [
  ["Kevindoto / Weeknd third on Spotify", "0.453", "0.112", "0.339", "0.999", "YES won"],
  ["Kevindoto / Drake third on Spotify", "0.409", "0.110", "0.357", "0.999", "NO won"],
  ["AllYourMonies / BTS sales below 3m", "0.716", "0.497", "0.750", "0.999", "YES won"],
  ["cookiejar / Beast Games 151-175", "0.782", "0.500", "0.667", "0.999", "YES won"],
];

const taskRows = [
  [
    "1. Data collection",
    "Collected public Polymarket market metadata, trade records, wallet profile statistics, and public trade API refreshes for the selected contracts. The reviewed universe covers 154 resolved markets across 42 events, $211.9 million of market lifetime volume, and 205,362 pulled trades from 44,607 wallets.",
    "markets_reviewed.csv, trades.csv.gz, wallets.csv, candidate_market_movements.csv",
  ],
  [
    "2. Heuristic design",
    "Used explainable indicators rather than a black-box model: specific information owner, non-obvious entry price, clustered or paired conviction, wallet-relative abnormality, wash/noise filtering, and post-entry contract movement.",
    "heuristics.md, score_wallets.py, identify_candidate_leads.py",
  ],
  [
    "3. Application to traders",
    "Applied the screen to wallet-market clusters and manually reviewed the strongest candidates. The final memo elevates three wallets and four wallet-market positions, with contract movement checked directly against the free Polymarket trade API.",
    "candidate_wallet_leads.csv, candidate_market_price_points.csv, candidate_market_movements.png",
  ],
  [
    "4. Ranking and methodology",
    "Kept a broad scoring output for review, then separated the final candidate queue from older wallet-tagging experiments. The ranking is qualitative but auditable: Kevindoto for paired Spotify positioning, AllYourMonies for size anomaly, and cookiejar for production-access logic.",
    "wallet_scores_reviewed.csv, top20_reviewed.csv, verification_summary.json, personal_learnings/legacy_wallet_tags/",
  ],
];

const children = [
  h1("Potential Informed Trading on Polymarket"),
  para([text("Anthony Lin", { bold: true }), text(" | Inca Digital Investigations Analyst Take-Home | May 28, 2026")]),
  h2("Executive View"),
  para([
    text("I would submit three potential insider-trading candidates from the reviewed market set. "),
    text("Kevindoto", { bold: true }),
    text(" is the best market-structure lead because the wallet expressed a paired view inside the same Spotify ranking complex: The Weeknd would finish third and Drake would not. "),
    text("AllYourMoniesAreBelongToMe", { bold: true }),
    text(" is the best size-anomaly lead because the BTS album-sales position was roughly 116 times the wallet's prior median trade size. "),
    text("cookiejar", { bold: true }),
    text(" is the cleanest production-access lead because it bought a Beast Games result market 38 to 48 days before resolution, when the show result was likely already known inside the production chain."),
  ]),
  note("The core idea is not \"large wallet won a trade.\" These wallets entered correct-side positions in markets where a specific group could plausibly know the answer earlier than the public: streaming platforms, labels, distributors, chart vendors, or production teams."),

  h2("Screen and Heuristics"),
  para("I reviewed 154 resolved markets across 42 events, covering $211.9 million of market lifetime volume and 205,362 pulled trades from 44,607 wallets. The pipeline uses a stricter ranking screen for the whole wallet universe and a wider triage screen for manual candidate review. The triage screen keeps clusters where the wallet bought the ultimately winning contract at 20 to 85 cents, at least 24 hours before resolution, with at least $3,000 of notional buying in that market."),
  table(["Heuristic", "Why it matters", "Candidate hit"], heuristicsRows, [2200, 4000, contentWidth - 6200]),

  h2("Candidate Detail"),
  table(["Priority", "Wallet", "Position", "Why it looks insider-shaped"], candidateRows, [700, 2300, 3100, contentWidth - 6100]),

  h2("Contract Movement and Resolution"),
  para("The free Polymarket trade API shows that these were not simple endgame sweeps. The contracts still moved against the candidate wallets after entry, then confirmed into resolution."),
  table(["Wallet / market", "Entry avg.", "Worst after first buy", "Worst after last buy", "Last pre-resolution", "Resolution"], movementRows, [2700, 1250, 1750, 1750, 1650, contentWidth - 9100]),
  new Paragraph({
    children: [
      new ImageRun({
        data: fs.readFileSync(CHART),
        transformation: { width: 650, height: 329 },
      }),
    ],
    spacing: { before: 80, after: 80 },
  }),

  h2("Interpretation"),
  para("The notional floors used here ($5,000 for ranking, $3,000 for triage) are not too low for this kind of work. A pure whale threshold would miss stealthier insider behavior, and Polymarket wallets can be meaningful even when the notional looks modest in institutional terms. For this assignment, the better signal is a bundle: correct side, non-obvious price, specific information owner, abnormal wallet behavior, and favorable contract movement after entry."),
  para("Timing also depends on the market. A production-result trade can be suspicious weeks before resolution because the result may already be fixed internally. A streaming-rank trade may cluster closer to resolution because the informational edge comes from late internal dashboards or ranking snapshots. These three wallets fit those different timing patterns."),

  h2("Submission Methodology Appendix"),
  para("This section is included so the memo can be submitted without sharing the GitHub repository. It maps the analysis directly to the four requested assignment tasks and names the supporting artifacts that can be attached separately if requested."),
  table(["Assignment task", "What I did", "Supporting artifact"], taskRows, [2000, 5600, contentWidth - 7600]),
  para("Recommended submission package: send this Word document, optionally export it to PDF, and attach only the small supporting CSVs if the interviewer asks for reproducibility. I would not share the full GitHub repository unless specifically requested, because the repo contains personal learning files and intermediate experiments that are not part of the polished submission.", { after: 0 }),
];

const doc = new Document({
  styles: {
    default: {
      document: { run: { font: "Arial", size: 20, color: colors.ink } },
    },
    paragraphStyles: [
      {
        id: "Heading1",
        name: "Heading 1",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { size: 34, bold: true, font: "Arial", color: colors.deep },
        paragraph: { spacing: { before: 0, after: 120 }, outlineLevel: 0 },
      },
      {
        id: "Heading2",
        name: "Heading 2",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { size: 24, bold: true, font: "Arial", color: colors.green },
        paragraph: { spacing: { before: 220, after: 80 }, outlineLevel: 1 },
      },
    ],
  },
  sections: [{ properties: { page }, children }],
});

Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync(OUT, buffer);
  console.log(OUT);
});
