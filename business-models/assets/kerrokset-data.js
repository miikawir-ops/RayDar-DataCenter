// Geometry for the layered responsibility view on the hub (ledger R61).
// Measured on the frozen image assets/datakeskus-kerrokset.webp (1672 x 941 px;
// source docs/briefs/datakeskus-kerrokset-original.png). Every coordinate is in
// image pixels, which is also the overlay SVG's viewBox, so the zones can't drift
// from the artwork. Re-measure all of it if the image ever changes.
// All text lives in index.html (the staircase table is the single source for who
// handles what); this file holds coordinates and the per-model structure only.
window.BM_LAYERS = {
  width: 1672,
  height: 941,
  // Zones top to bottom (brief: Z1-Z6). rows = staircase rows (1-14) in the zone.
  // poly = clickable area; label = where the zone's label sits (left edge, top);
  // site = part of the building and its plot (Z4-Z6). leader = where the callout's
  // leader line starts, when the rightmost corner won't do (Z2: from its corner the
  // leader crossed the public cloud's 'Vastuuraja, tyypillisesti' label; R69).
  // Z4 covers the caged racks only: the free-standing white units on that floor
  // (x 905-990) are in-row cooling, and cooling is row 8 (Z5).
  zones: {
    // Z1 follows the slab and the tops of the floating panels and the cloud, not a
    // hull over them (R69: the hull read as a grey roof the picture doesn't have).
    z1: { rows: [1, 2, 3],        label: [1090, 52],
          poly: [[300,148],[300,128],[385,112],[385,58],[487,50],[507,28],[552,28],[600,17],[650,17],[690,30],[710,14],[835,30],[835,50],[882,60],[885,82],[947,90],[998,145],[998,160],[700,218]] },
    z2: { rows: [4],              label: [1090, 178], leader: [998, 201],
          poly: [[300,148],[700,218],[998,160],[998,242],[700,306],[300,234]] },
    z3: { rows: [5, 6],           label: [1090, 282],
          poly: [[303,236],[700,306],[998,242],[998,330],[1023,346],[1023,358],[695,440],[279,347],[282,336],[303,256]] },
    z4: { site: true, rows: [7],              label: [1090, 418],
          poly: [[270,352],[695,442],[905,390],[905,512],[660,560],[272,470]] },
    z5: { site: true, rows: [8, 9, 10],       label: [1090, 548],
          poly: [[255,478],[658,592],[1032,492],[1045,515],[1045,628],[676,727],[245,580]] },
    z6: { site: true, rows: [11, 12, 13, 14], label: [1090, 652],
          poly: [[245,585],[676,730],[1045,632],[1045,725],[1110,745],[1160,790],[980,860],[640,920],[215,800],[215,655]] }
  },
  // Demarc lines run along the lower front edges of the slabs (the gap below
  // each zone): g12 = between Z1 and Z2, and so on. g1x and g1t are inside Z1:
  // the public cloud's PaaS and SaaS positions (R66), g1t near the top, parallel
  // to the others; both shortened to stay inside the trimmed Z1 (R69).
  gaps: {
    g1t: [[392,70],[700,122],[895,84]],
    g1x: [[392,112],[700,166],[960,115]],
    g12: [[300,152],[700,222],[998,164]],
    g23: [[300,238],[700,310],[998,246]],
    g34: [[279,350],[695,444],[1023,361]],
    g45: [[255,482],[658,596],[1032,496]],
    g56: [[245,584],[676,731],[1045,632]]
  },
  // Per model: own = zones the company typically handles itself; lines = the
  // demarc line(s), [gap, label key]; range = [upper, lower] gap of the band
  // the line moves in (cloud models only); positions = named service models on
  // the band, [gap, label key] (public cloud: IaaS, PaaS, SaaS; R66).
  models: {
    "public-cloud":         { own: ["z1"],                         lines: [["g12", "typical"]],  range: ["g1t", "g12"],
                            positions: [["g12", "iaas"], ["g1x", "paas"], ["g1t", "saas"]] },
    "gpu-cloud":            { own: ["z1", "z2"],                   lines: [["g23", "typical"]],  range: ["g12", "g23"] },
    "retail-colocation":    { own: ["z1", "z2", "z3"],             lines: [["g34", "line"]] },
    "wholesale-colocation": { own: ["z1", "z2", "z3", "z4"],       lines: [["g45", "turnkey"], ["g56", "shell"]] },
    "own-data-center":      { own: ["z1", "z2", "z3", "z4", "z5", "z6"], lines: [] }
  },
  // Fixed markers: the grid connection point (same in every model) where the
  // lines from the pylons reach the substation fence; the waste-heat hotspot on
  // the red/blue district heating pipe toward the town.
  grid: { at: [228, 662], label: [24, 590] },
  heat: { at: [1040, 790], label: [1180, 812],
          poly: [[893,813],[906,840],[1010,808],[1110,778],[1162,764],[1166,745],[1150,728],[1100,712],[1050,700],[1046,712],[1098,727],[1140,742],[1138,752],[1090,762],[1000,787]] }
};
