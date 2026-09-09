# Using the graphics without writing code

This guide is for editors, researchers, and organizers. You can describe the
graphic you want in ordinary language; an AI agent can operate the build tools
for you.

## Start by choosing publishing mode

Tell the agent:

> Work with me in publishing mode. I will describe the story and visual result;
> you handle the code and show me the exported graphic.

Useful requests include:

- “List the graphics currently available.”
- “Build every Instagram post.”
- “Build only the proposed-use map for Instagram.”
- “Change this title, then show me the rebuilt image.”
- “Make the map more prominent without shrinking its legend.”
- “Use this statistic in Detroit's lower-right map pocket.”

The agent should make changes in the graphic's canonical definition, rebuild
the requested output, and show you the PNG when visual review is useful. You
should not need to edit HTML, SVG, or Python yourself.

## What is safe to change

Each graphic owns its story and its data choices. You can ask to change:

- title, subtitle, source attribution, or description;
- categories, labels, colors, ordering, or explanatory text;
- which data is shown and how it is summarized;
- map dots, legends, hero figures, and map-pocket content;
- bar direction, label angle, and other exposed chart options;
- the target: Instagram post, Instagram Story, or land-use conference.

The same graphic definition fans out to every target. A change should not be
made by editing an exported image.

## Review checklist

Before approving a graphic, check:

1. Does the title state the intended finding accurately?
2. Can the map or chart be understood on a phone?
3. Are the legend and important labels legible?
4. Do quantities, categories, and denominators mean what a reader will assume?
5. Are the source and date range correct?
6. Does the Instagram version preserve the essential story rather than merely
   shrinking a conference poster?

If a request would alter the shared library or affect other graphics, the
agent should explain that boundary and ask before making a major interface or
architectural decision.

## Build commands

You may ask an agent to run these; you do not need to run them yourself.

```bash
# See available definitions
strongtowns assets list

# Check that the required data is ready
strongtowns assets check

# Build all graphics in all publishing formats
strongtowns assets build

# Build one graphic for Instagram
strongtowns assets build bza_proposed_use_map --target instagram
```

Run these from the Detroit project checkout, or have the agent supply its path
with `--project`. The `assets` commands check each graphic's required data before
rendering. If an input is missing, ask the project maintainer or agent to resolve
it; these commands do not download or prepare missing data automatically.

Exports appear under `projects/graphics/output/<target>/<definition>/`.
That directory is generated and should never be edited by hand.
