// Communities and apartment models for the public room experience.
//
// ONLY two kinds of entry are allowed (lib/roomExperience/model.js validates):
//   dataStatus "demo"      invented sample data to exercise the UI. Must say so
//                          in its name, and is labelled "Demo data" everywhere.
//   dataStatus "verified"  real community data. REQUIRES `source` (publisher,
//                          url, retrievedAt) for the floor plans and square
//                          footage, taken from the community's own published
//                          material. Never scrape, estimate or invent these.
//
// A model shows its real floor-plan image when `floorPlan.imageUrl` is set
// (put the file in frontend/public/media/floorplans/). Otherwise the page draws
// the simple `schematic`, which is always labelled "Schematic, not to scale".
//
// schematic units: an abstract 100 x 70 grid (not feet).
//   rooms:    labelled rectangles
//   fixtures: room objects CAOSCare features attach to — window, tv, lamp,
//             thermostat, bed, chair (ids referenced by features.js `fixtures`)

export const COMMUNITIES = [
  {
    id: "sample-community",
    name: "Sample Community (demo)",
    location: "Demo data — not a real community",
    dataStatus: "demo",
    source: null,
    models: [
      {
        id: "sample-studio",
        name: "Studio (sample)",
        bedrooms: 0,
        bathrooms: 1,
        squareFeet: 450,
        floorPlan: { imageUrl: null, imageAlt: "" },
        schematic: {
          rooms: [
            { id: "main", label: "Living / sleeping", x: 0, y: 0, w: 70, h: 70 },
            { id: "bath", label: "Bath", x: 70, y: 0, w: 30, h: 35 },
            { id: "entry", label: "Entry", x: 70, y: 35, w: 30, h: 35 },
          ],
          fixtures: [
            { kind: "window", x: 30, y: 2 },
            { kind: "bed", x: 18, y: 22 },
            { kind: "lamp", x: 6, y: 12 },
            { kind: "chair", x: 32, y: 52 },
            { kind: "tv", x: 52, y: 60 },
            { kind: "thermostat", x: 58, y: 30 },
          ],
        },
      },
      {
        id: "sample-one-bedroom",
        name: "One Bedroom (sample)",
        bedrooms: 1,
        bathrooms: 1,
        squareFeet: 650,
        floorPlan: { imageUrl: null, imageAlt: "" },
        schematic: {
          rooms: [
            { id: "bedroom", label: "Bedroom", x: 0, y: 0, w: 45, h: 70 },
            { id: "living", label: "Living room", x: 45, y: 0, w: 55, h: 45 },
            { id: "bath", label: "Bath", x: 45, y: 45, w: 25, h: 25 },
            { id: "kitchen", label: "Kitchenette", x: 70, y: 45, w: 30, h: 25 },
          ],
          fixtures: [
            { kind: "window", x: 20, y: 2 },
            { kind: "bed", x: 20, y: 35 },
            { kind: "lamp", x: 6, y: 20 },
            { kind: "window", x: 75, y: 2 },
            { kind: "chair", x: 62, y: 25 },
            { kind: "lamp", x: 52, y: 12 },
            { kind: "tv", x: 90, y: 25 },
            { kind: "thermostat", x: 47, y: 40 },
          ],
        },
      },
    ],
  },
];
