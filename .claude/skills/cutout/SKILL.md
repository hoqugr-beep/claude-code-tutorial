---
name: cutout
description: Remove the background from a photo and deliver a clean transparent PNG of the subject, trimmed to its bounds and visually verified. Use this whenever someone wants a background removed, a person or subject "cut out", a knockout, an isolated subject, or a transparent PNG — including when they just drop a photo in and say "cut this out", or invoke /cutout. Also use it when a design task needs a subject lifted off its background before compositing (commitment graphics, posters, flyers, social posts, thumbnails), even if the user never says the word "cutout".
---

# Cutout

Turn a photo into a transparent PNG of its subject, ready to composite into a
design.

The work itself is one model call. What separates a usable cutout from a
worthless one is everything around that call: confirming you actually have the
file, picking a model that keeps what matters, and *looking* at the result
before handing it over.

## 1. Get the image — and confirm you really have it

If the user has not already supplied a photo, ask for one:

> Drop the photo into the chat and I'll cut the subject out of it.

Then **verify the file exists on disk before doing anything else**:

```bash
ls -la /root/.claude/uploads/*/ 2>/dev/null
find / -xdev \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' \) \
  -newermt '-10 minutes' 2>/dev/null | grep -v -E 'node_modules|/usr/share|/opt/|site-packages' | head
```

This step is not paranoia. **Seeing an image in the conversation and having the
file are different things**, and they come apart regularly — an attachment can
render perfectly for you while nothing is written to the filesystem. If you skip
this check you will happily plan an entire pipeline around bytes you cannot
open, and only discover it several steps later.

If the file is not on disk, say so immediately and plainly — "I can see it but
it didn't reach the filesystem" — and offer routes that deliver actual bytes:
re-attaching, a cloud-storage connector you have verified works, or a repo the
user can upload to. Do not guess at the pixels and do not proceed as if you have
the image.

Confirm what you found before continuing:

```bash
python3 -c "from PIL import Image; im=Image.open('PATH'); print(im.size, im.mode)"
```

## 2. Run the cutout

```bash
pip install --quiet rembg pillow          # first time only
python3 scripts/cutout.py PHOTO -o OUT_DIR
```

The first run downloads a model (~100–200 MB) from GitHub and can take a couple
of minutes before it prints anything; subsequent runs are fast. Run it in the
background rather than letting a foreground timeout kill it mid-download. If
GitHub is blocked, jump to **Fallbacks** below.

By default the script runs two general-purpose models and writes, for each:

- `cutout-<model>.png` — the deliverable, trimmed to the subject
- `check-<model>.png` — the same cutout composited across a split white/dark
  ground, for inspection

## 3. Choose the model deliberately

Model choice is the decision most likely to ruin the result, and the intuitive
choice is often wrong.

**Prefer a general salient-object model (`u2net`, `isnet-general-use`) over a
human-segmentation model (`u2net_human_seg`) whenever the subject is holding or
wearing something that belongs in the shot.** Human segmentation models are
trained to find *the human* — so they amputate a lacrosse stick, a tennis
racket, a guitar, a held trophy. For an athlete the equipment is usually the
whole point of the photo, and losing it is not a subtle flaw. General models
treat the person-plus-equipment as one salient object and keep it.

This is not theoretical. On a lacrosse player mid-stride, `u2net` and
`isnet-general-use` both kept the full stick; `u2net_human_seg` on the same
frame deleted the stick head, most of the shaft, and part of the hand gripping
it — leaving her reaching at nothing. The failure is obvious once you look at
the render and invisible if you only check that a file was produced.

Reach for `u2net_human_seg` only when you specifically want the person alone and
the background contains distracting objects near them.

## 4. Look at the result — actually look

Read each `check-*.png` with the image viewer. This is the step people skip and
it is the only one that catches real failures. Each render puts the subject
across a white half and a dark half, because the two common edge faults hide on
opposite grounds — a pale halo vanishes on dark and screams on white, dark
fringing does the reverse. Scan both halves.

You are looking for:

- **Amputated limbs or equipment** — the most damaging failure
- **A soft glow around the subject** — the edge should meet the background
  decisively, not fade into it. On the white half this looks like the subject is
  lit from behind. It is the most common quality problem and the easiest to fix.
- **Chewed hair edges** — the opposite fault, from an over-tight matte
- **Background left in enclosed gaps** — between arm and torso, inside a stick
  head, between legs
- **Colour fringing** from the old background bleeding into the edge

If both models produced a clean mask, either is fine — say so rather than
inventing a distinction. If one dropped something the other kept, that decides
it.

The script prints a `soft/opaque` ratio per model — the share of pixels that are
partially transparent, which is a direct measure of how wide the feathered edge
band is. Under ~0.15 is crisp; above ~0.30 there is almost certainly a visible
glow. Treat it as a pointer to where to look, not a verdict: some softness on
flyaway hair is correct, and a suspiciously low ratio on a subject with loose
hair means the matte chewed it off.

**If the edges glow, lower `--erode-size` first.** It is by far the most
sensitive knob — it erodes the mask inward before matting, so a large value
carves into the subject and forces a wide soft band to bridge the gap. Dropping
it from 8 to 3 on a light subject halved the soft/opaque ratio (0.27 → 0.12) and
turned a visibly haloed cutout into a clean one. Nudge `--fg-threshold` down and
`--bg-threshold` up only after that.

**Do not "fix" a halo by disabling alpha matting.** It sounds like it should
give a harder edge and it does the opposite: without matting the raw model
output is a soft probability map, so nearly every pixel comes back partially
transparent and the whole subject turns ghostly. Matting with tight settings is
what produces a decisive edge.

## 5. Deliver

Send the chosen `cutout-<model>.png` with the file-delivery tool available to
you, and say briefly what survived — "stick, hair bun and goggle strap all
intact" tells the user more than "done".

Mention the pixel dimensions. Downstream design work needs to know whether the
cutout is big enough for the placement, and a subject trimmed to its bounds is
usually much smaller than the source photo.

Keep the delivered file **untinted and unlit** — no rim glow, no colour grading,
no drop shadow. Those are design decisions that belong to whatever composition
consumes this, and baking them in makes the asset single-use. A clean cutout
composites into anything; a maroon-tinted one with a white halo only works on
one background.

## Fallbacks when `rembg` is unavailable

If the model download is blocked or the install fails, background removal is
available through several connectors. Check which are actually connected before
promising one:

- **Adobe** — `image_remove_background` (needs the image reachable as a URL or
  uploaded asset)
- **Higgsfield** — `remove_background`
- **Canva** — background removal within a design

Each needs the image to reach *their* servers, so if the blocker was network
egress rather than the install, a connector may fail the same way. Say which one
you are trying and why, so a second failure is informative rather than baffling.

## Notes

- The script trims to the subject's alpha bounds by default. This makes
  placement predictable downstream — you position a known shape rather than a
  mostly-empty canvas. Pass `--no-trim` to keep the original framing when the
  caller needs the subject registered to the source dimensions.
- Alpha-matting defaults (`--fg-threshold 250 --bg-threshold 15 --erode-size 8`)
  are tuned for a well-lit subject against a moderately busy background. They
  are a reasonable starting point, not a rule.
- Upscaling a cutout does not add detail. If the subject is too small for its
  intended placement, ask for a higher-resolution source rather than enlarging.
