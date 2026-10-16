import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { useBoxDrag } from "../useBoxDrag";

// Owner rule (#153 slice 2): only a box's drag handle moves it; pressing and
// dragging anywhere else on the box (title, number, controls) leaves the order alone.
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const BOXES = [{ id: "a" }, { id: "b" }];
let container, root, commit;

function Grid() {
  const { shown, onPointerDown } = useBoxDrag(BOXES, commit);
  return shown.map((b) => (
    <article key={b.id} data-box-id={b.id} data-testid={`box-${b.id}`} onPointerDown={onPointerDown(b.id)}>
      <button type="button" data-drag-handle data-testid={`grip-${b.id}`}>grip</button>
      <h3 data-testid={`title-${b.id}`}>{b.id}</h3>
    </article>
  ));
}

const fire = (target, type, x, y) => target.dispatchEvent(new MouseEvent(type, { bubbles: true, button: 0, clientX: x, clientY: y }));
function dragFrom(el, over) {
  document.elementFromPoint = () => over;
  act(() => { fire(el, "pointerdown", 10, 10); });
  act(() => { fire(window, "pointermove", 40, 40); });
  act(() => { fire(window, "pointerup", 40, 40); });
}

beforeEach(() => {
  commit = jest.fn();
  container = document.createElement("div"); document.body.appendChild(container);
  root = createRoot(container); act(() => root.render(<Grid />));
});
afterEach(() => { act(() => root.unmount()); container.remove(); });

test("dragging by the handle reorders the boxes", () => {
  dragFrom(container.querySelector('[data-testid="grip-a"]'), container.querySelector('[data-testid="box-b"]'));
  expect(commit).toHaveBeenCalledTimes(1);
  expect(commit.mock.calls[0][0].map((b) => b.id)).toEqual(["b", "a"]);
});

test("dragging from the box body does not move it", () => {
  dragFrom(container.querySelector('[data-testid="title-a"]'), container.querySelector('[data-testid="box-b"]'));
  expect(commit).not.toHaveBeenCalled();
});
