import { itemsLine, cleanItems } from "../requestItems";

test("items read as quantity × item", () => {
  expect(itemsLine([{ item: "towels", quantity: 2 }, { item: "warm blanket", quantity: 1 }])).toBe("Items: 2 × towels, 1 × warm blanket");
  expect(itemsLine([])).toBeNull();
});

test("only well-formed items are sent", () => {
  expect(cleanItems([{ item: " towels ", quantity: "2" }, { item: "", quantity: 1 }, { item: "soap", quantity: 99 }]))
    .toEqual([{ item: "towels", quantity: 2 }, { item: "soap", quantity: 20 }]);
  expect(cleanItems(undefined)).toBeUndefined();
  expect(cleanItems([])).toBeUndefined();
});
