import { ReelMotion, fitRatio, isReelTarget, neighborTarget, reelPose } from "./title-reel";

/** Presentation only. The existing lens buttons remain the single state owner. */
export function mountTitleReels(doc: Document) {
  doc.querySelectorAll<HTMLElement>("[data-title-reel]").forEach(root => {
    if (root.classList.contains("is-ready")) return;
    const win = doc.defaultView;
    const faces = [...root.querySelectorAll<HTMLElement>("[data-reel-face]")];
    const stage = root.querySelector<HTMLElement>("[data-reel-stage]");
    const inputs = root.querySelector<HTMLElement>("[data-reel-inputs]");
    const before = root.querySelector<HTMLElement>("[data-reel-before]");
    const after = root.querySelector<HTMLElement>("[data-reel-after]");
    const status = root.querySelector<HTMLElement>("[data-reel-status]");
    if (!win || faces.length !== 6 || !stage || !inputs || !before || !after || !status) return;
    const motionQuery = win.matchMedia("(prefers-reduced-motion: reduce)");
    const buttons = [...inputs.querySelectorAll<HTMLButtonElement>("[data-reel-step]")];
    const name = (target: string) => faces.find(face => face.dataset.target === target)?.dataset.name ?? target;
    const activeIndex = (destination: number) => ((Math.round(destination) % 6) + 6) % 6;
    const updateHits = (destination: number) => {
      const frame = root.getBoundingClientRect();
      if (!frame.width) return;
      for (const direction of [-1, 1]) {
        const caption = direction === -1 ? before : after;
        const rects = [caption.getBoundingClientRect()];
        const face = faces[(activeIndex(destination) + direction + 6) % 6];
        if (Number(face.style.opacity) > 0) face.querySelectorAll<HTMLElement>(".title-line").forEach(line => {
          const range = doc.createRange(); range.selectNodeContents(line); rects.push(range.getBoundingClientRect());
        });
        const hit = inputs.querySelector<HTMLElement>(direction === -1 ? ".top" : ".bottom");
        if (!hit) continue;
        const top = Math.min(...rects.map(rect => rect.top)), bottom = Math.max(...rects.map(rect => rect.bottom));
        hit.style.top = `${top - frame.top - 3}px`;
        hit.style.height = `${Math.max(24, bottom - top + 6)}px`;
      }
    };
    let labelledTarget = "";
    const draw = (position: number, destination: number, target: string) => {
      root.dataset.reelTarget = target;
      root.dataset.reelPosition = String(position);
      root.dataset.reelDestination = String(destination);
      faces.forEach((face, index) => {
        const pose = reelPose(position, index);
        face.style.transform = `translate3d(0,${pose.y}px,${pose.z}px) rotateX(${-pose.angle}deg) scale(${pose.scale})`;
        face.style.opacity = String(pose.opacity);
        face.classList.toggle("is-active", index === activeIndex(destination));
      });
      if (isReelTarget(target) && labelledTarget !== target) {
        labelledTarget = target;
        before.textContent = `${root.dataset.previewLabel} / ${name(neighborTarget(target, -1))}`;
        after.textContent = `${root.dataset.previewLabel} / ${name(neighborTarget(target, 1))}`;
        buttons.forEach(button => {
          const direction = Number(button.dataset.reelStep);
          button.setAttribute("aria-label", `${direction === -1 ? root.dataset.previousLabel : root.dataset.nextLabel}: ${name(neighborTarget(target, direction))}`);
        });
      }
      updateHits(destination);
    };
    const motion = new ReelMotion(draw, {
      now: () => win.performance.now(), request: cb => win.requestAnimationFrame(cb), cancel: id => win.cancelAnimationFrame(id),
    });
    const request = (direction: number) => {
      // Calling the existing button preserves publications, PDF-menu, storage
      // and every other cv-target-change consumer, without a second state path.
      doc.querySelector<HTMLButtonElement>(`[data-cv-target="${neighborTarget(motion.target, direction)}"]`)?.click();
    };
    buttons.forEach(button => button.addEventListener("click", () => request(Number(button.dataset.reelStep))));
    inputs.addEventListener("keydown", event => {
      if (event.altKey || event.ctrlKey || event.metaKey || !["ArrowUp", "ArrowDown"].includes(event.key)) return;
      event.preventDefault(); request(event.key === "ArrowUp" ? -1 : 1);
    });
    win.addEventListener("cv-target-change", event => {
      const detail = (event as CustomEvent).detail;
      if (!isReelTarget(detail?.target) || detail.target === motion.target) return;
      motion.select(detail.target, detail.animate !== false && !motionQuery.matches);
      // One live region, one change per user selection; restore and resize are silent.
      if (detail.animate !== false) status.textContent = `${name(detail.target)}: ${root.querySelector("h1")?.textContent}`;
    });
    motionQuery.addEventListener("change", () => { if (motionQuery.matches) motion.snap(); });
    stage.hidden = false; inputs.hidden = false; root.classList.add("is-ready");
    const selected = doc.querySelector<HTMLButtonElement>('[data-cv-target][aria-pressed="true"]')?.dataset.cvTarget;
    if (isReelTarget(selected)) motion.select(selected, false);
    else motion.snap();
    const fit = () => {
      faces.forEach(face => face.querySelectorAll<HTMLElement>(".title-line").forEach(line => {
        line.style.removeProperty("--reel-fit");
        // offsetWidth measures unprojected text, unlike transformed glyph rects.
        const word = line.querySelector<HTMLElement>("[data-title-word]");
        if (word) line.style.setProperty("--reel-fit", String(fitRatio(line.clientWidth, word.offsetWidth)));
      }));
      updateHits(motion.destination);
    };
    new ResizeObserver(fit).observe(root);
    void doc.fonts.ready.then(fit);
    doc.fonts.addEventListener("loadingdone", fit);
    fit();
  });
}
