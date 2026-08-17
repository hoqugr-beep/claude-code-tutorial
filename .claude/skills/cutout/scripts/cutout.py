#!/usr/bin/env python3
"""Remove an image background and write a trimmed transparent PNG.

For each model requested this writes two files:

  cutout-<model>.png  the deliverable: transparent, trimmed to the subject
  check-<model>.png   an inspection render: the cutout composited across a
                      split light/dark background

The check render exists because a transparent PNG viewed on its own tells you
almost nothing -- a missing arm and a clean cut look identical against a
checkerboard. The background is split light/dark because the two common edge
faults hide on opposite grounds: a pale halo is invisible on dark and obvious on
white, while dark fringing from the old background is the reverse.

Usage:
    python cutout.py PHOTO [-o OUT_DIR] [-m u2net,isnet-general-use]
                          [--check-bg "#8A222A"] [--no-trim]
"""
import argparse
import os
import sys


def build_parser():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("image", help="path to the source photo")
    p.add_argument("-o", "--out-dir", default=".", help="where to write results")
    p.add_argument(
        "-m", "--models", default="u2net,isnet-general-use",
        help="comma-separated rembg models. Default runs two general "
             "salient-object models so their masks can be compared.")
    p.add_argument("--check-bg", default="#1C1C1C",
                   help="dark half of the inspection render (light half is white)")
    p.add_argument("--no-trim", action="store_true",
                   help="keep the original canvas instead of cropping to the subject")
    # Defaults tuned on a light subject against a bright background. erode-size
    # is the sensitive one: at 8 it bites into the subject and forces a wide
    # feathered band that reads as a glow once composited.
    p.add_argument("--fg-threshold", type=int, default=240)
    p.add_argument("--bg-threshold", type=int, default=20)
    p.add_argument("--erode-size", type=int, default=3)
    p.add_argument("--check-height", type=int, default=900)
    return p


def hex_to_rgb(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def main():
    args = build_parser().parse_args()

    try:
        from PIL import Image
        from rembg import new_session, remove
    except ImportError as e:
        sys.exit(
            f"Missing dependency ({e.name}). Install with:\n"
            "    pip install --quiet rembg pillow\n"
            "First run also downloads the model (~100-200 MB) from GitHub. If "
            "that host is blocked, use a connector-based remover instead -- see "
            "the skill's fallback section.")

    if not os.path.isfile(args.image):
        sys.exit(f"No such file: {args.image}\n"
                 "The image must exist on disk. Being able to SEE an image in "
                 "the conversation does not mean it was written to the "
                 "filesystem -- confirm the path before running this.")

    os.makedirs(args.out_dir, exist_ok=True)
    src = Image.open(args.image).convert("RGB")
    print(f"source: {args.image} {src.size}")

    bg = hex_to_rgb(args.check_bg)
    results = []

    for model in [m.strip() for m in args.models.split(",") if m.strip()]:
        try:
            print(f"\n[{model}] loading session", flush=True)
            session = new_session(model)
            print(f"[{model}] removing background", flush=True)
            out = remove(
                src,
                session=session,
                alpha_matting=True,
                alpha_matting_foreground_threshold=args.fg_threshold,
                alpha_matting_background_threshold=args.bg_threshold,
                alpha_matting_erode_size=args.erode_size,
            )
        except Exception as e:
            print(f"[{model}] FAILED {type(e).__name__}: {e}", flush=True)
            continue

        bbox = out.getchannel("A").getbbox()
        if bbox is None:
            print(f"[{model}] produced an empty mask -- nothing detected")
            continue
        if not args.no_trim:
            out = out.crop(bbox)

        cut_path = os.path.join(args.out_dir, f"cutout-{model}.png")
        out.save(cut_path)

        # Inspection render: subject across a split white/dark ground, so a pale
        # halo and dark fringing are both visible in one image.
        view = out
        if view.height > args.check_height:
            w = round(view.width * args.check_height / view.height)
            view = view.resize((w, args.check_height), Image.LANCZOS)
        plate = Image.new("RGBA", view.size, (255, 255, 255, 255))
        dark = Image.new("RGBA", (view.width // 2, view.height), bg + (255,))
        plate.paste(dark, (view.width - dark.width, 0))
        plate.alpha_composite(view)
        check_path = os.path.join(args.out_dir, f"check-{model}.png")
        plate.convert("RGB").save(check_path)

        alpha = out.getchannel("A")
        hist = alpha.histogram()
        soft = sum(hist[1:255])          # partially transparent = matted edge
        opaque = hist[255]
        ratio = soft / max(1, opaque)
        verdict = ("crisp" if ratio < 0.15 else
                   "soft - check for a halo" if ratio < 0.30 else
                   "very soft - likely a visible glow, retune before shipping")
        print(f"[{model}] subject bbox {bbox} -> {out.size}")
        print(f"[{model}] opaque {opaque:,} | soft {soft:,} | "
              f"soft/opaque {ratio:.3f} ({verdict})")
        print(f"[{model}] wrote {cut_path}")
        print(f"[{model}] wrote {check_path}  <-- LOOK AT THIS ONE")
        results.append((model, cut_path, check_path))

    if not results:
        sys.exit("\nNo model produced a usable mask.")

    print("\nDone. Open each check-*.png and compare before choosing a winner.")
    print("Look specifically for: amputated limbs, dropped equipment held by "
          "the subject, chewed hair edges, and background colour left in gaps "
          "(between arm and torso, inside a stick head).")


if __name__ == "__main__":
    main()
