---
name: designing-matchnight-ui
description: Use when designing or building any dashboard screen, component, chart, animation, copy or visual asset for the Champions League prediction app, including the what-if score editor, probability table, bracket and team pages.
---

# Designing the Matchnight UI

## Overview

The dashboard should feel like a **European night under floodlights**, and still read like a precise instrument. The atmosphere sits in the background. The probabilities are always the sharpest thing on screen.

**REQUIRED BACKGROUND:** Follow frontend-design:frontend-design's process: token plan → review against the brief → build → screenshot and critique. **REQUIRED SUB-SKILL:** Use dataviz for every chart, bar, heatmap and stat tile.

## Starting tokens (confirm with the user before the first build)

| Token | Value | Role |
|---|---|---|
| `--night` | `#0B1736` | Page background: deep navy sky, not black |
| `--stand` | `#14244F` | Raised surfaces: table, panels |
| `--silver` | `#C9D3E6` | Secondary text, rules |
| `--floodlight` | `#F5F8FF` | Primary text, key numbers |
| `--beam` | `#7FD6FF` | Single accent: focus, "your what-if", the active path |
| `--rise` / `--fall` | Taken from dataviz's validated diverging pair | Probability up / down. Never pure red/green |

Type: one condensed display face with a stadium-signage feel (e.g. *Big Shoulders Display*) for headings and big numbers, and one clean text face (e.g. *Barlow*) for body. Use tabular figures for every number.

## Atmosphere (background layer only)

- **Sky:** a navy gradient with a sparse, static starfield. Stars never form a ball or any recognisable emblem.
- **Floodlights:** two or three large, soft radial glows from the top corners, low opacity.
- **Pitch:** faint centre-circle and halfway-line markings behind the league table, about 4% opacity.
- **Sound** (optional): ambient crowd murmur, **off by default**, with a visible toggle. Use only CC0 or self-made audio.

## The one bold moment: the what-if ripple

When the user enters a hypothetical score:
1. Re-simulate.
2. Table rows slide to their new order.
3. Each changed probability shows its delta in `--rise` or `--fall`, and the delta fades after ~2 s.
4. On the bracket, the affected paths brighten like floodlights switching on.

Everything else stays still. No entrance animations on every card. Under `prefers-reduced-motion`, there is no sliding or twinkle; the deltas still show.

## Screens

Matchday home (next fixtures with W/D/L bars) · League table with top 8 / 9–24 / out % · What-if lab · Probability bracket (play-off → final) · Team page (trend across snapshots, likely path) · Match page (scoreline heatmap, most likely scores *with* their %).

## Numbers and words

- Probabilities: whole % from 10–90; one decimal below 10% or above 90%; "<0.1%" / ">99.9%". Show **"Qualified"** or **"Out"** only when mathematically certain.
- Snapshot label on every view: "After matchday 4" or "Before matchday 1".
- One plain line, once: "Estimates from 50,000 simulations, not certainties."

## Brand and IP: hard rules

**Never use** UEFA's or the competition's logo, the starball, the anthem, the trophy's likeness, official fonts, or "Champions League" as the app's name or logo. Name the competition only in plain descriptive text. **Club crests are not used.** Teams appear as a colour chip + short code (e.g. `INT`, `PSG`) + name. Give the app its own original name and mark.

## Quality floor

Responsive to 375 px, visible keyboard focus, WCAG AA contrast on `--night`, a colour-blind-safe rise/fall pair, and every chart readable without hover.
