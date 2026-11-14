# Animated diagrams (`diagram` scenes)

A `diagram` scene draws nodes, groups and connectors and animates them on the narration's words: parts appear as
they are named, connectors draw from cause to effect, tokens carry requests and answers along them, and states
change as the story moves. Use it whenever the narration explains **how parts relate or how something happens over
time**. Motion here is explanation, not decoration: every movement should answer "what just happened, and to what?".

| The narration... | Use |
|---|---|
| names parts and how they connect, then something travels or changes between them | `diagram` |
| lists steps in order, nothing travels | `flow` (simpler) or a `diagram` with `layout: row` |
| needs a real shape, a place, a cross-section or a physical mechanism | `image` with an original drawing (`diagrams.md`) |
| contrasts two options | `compare`, or a `diagram` with two `groups` and `focus` |

## The data

```json
{"id": "s03", "type": "diagram", "heading": "What happens when you search",
 "say": "You type a question. Your browser sends it to the search engine, which checks its index and sends back the best pages.",
 "layout": "row",
 "nodes": [{"id": "you", "label": "You", "shape": "circle"},
           {"id": "browser", "label": "Browser"},
           {"id": "engine", "label": "Search engine"},
           {"id": "index", "label": "Index", "shape": "diamond"}],
 "groups": [{"id": "dc", "label": "Data centre", "nodes": ["engine", "index"]}],
 "edges": [{"id": "e1", "from": "you", "to": "browser"},
           {"id": "e2", "from": "browser", "to": "engine", "label": "HTTPS"},
           {"id": "e3", "from": "engine", "to": "index"}],
 "steps": [{"at": "You type", "show": ["you", "browser"]},
           {"at": "sends it", "show": ["engine"], "flow": {"edge": "e2", "label": "query"}},
           {"at": "checks its index", "show": ["index"], "activate": ["index"]},
           {"at": "sends back", "flow": {"edge": "e2", "reverse": true, "label": "best pages"}, "done": ["engine"]}]}
```

### Nodes, layout, groups, connectors

| Field | Meaning |
|---|---|
| `nodes[]` | `{id, label, x?, y?, shape?, sub?}`. `label` ≤ 3 words (`\n` for a second line); `sub` = small grey caption under it. `shape`: `box` (default: a thing, a component), `pill` (a service, an action), `circle` (a person, an actor, a start/end), `diamond` (a decision or a store, sparingly) |
| `layout` | `manual` (default: every node needs `x`, `y` in 0..1 of the area under the heading), `row` (left to right, spaced by real node sizes), `column`, `cycle` (a loop, 3-6 nodes), `hub` (`center` in the middle, the rest around it). Nodes with their own `x`, `y` keep them |
| `groups[]` | `{id, label?, nodes}`: a labelled frame around related nodes (a server, a device, "your computer") |
| `edges[]` | `{id?, from, to, route?, label?}`. `route`: `straight` (default), `curve` (two connectors between the same pair, or around something), `elbow` (right-angled, tidy for grids). `label` ≤ 2 words, shown on the connector once it has drawn. Without `id` the id is `from-to` |

Everything is kept inside the diagram area, with room for group frames. A row fits about 4 nodes in 16:9 (3 if
they are wide or labelled connectors sit between them); use `column` or `manual` for more, or two scenes.

### Steps: what happens on which words

Each step has `at` (a phrase from the scene's `say`, like every cue) and one or more actions. Ids in one action
enter one after another, `stagger` seconds apart (default 0.12).

| Action | Effect |
|---|---|
| `show: [ids]` | nodes and groups enter (fade + slight scale); connectors draw themselves |
| `draw: [edge ids]` | a connector draws from its start, the arrowhead travelling with the stroke |
| `hide: [ids]` | fade out |
| `activate` / `deactivate: [ids]` | lit in the accent colour with one soft pulse / back to idle |
| `done` / `error: [ids]` | the success / problem colour with a small ✓ / ✕ badge |
| `focus: [ids]` / `unfocus: true` | everything else steps back (dims); connectors between focused nodes stay; `unfocus` restores |
| `dim` / `undim: [ids]` | the same, for chosen elements |
| `label: {id: "new text"}` | a node's label crossfades in place ("Waiting" → "Done"); the node is sized for its longest label |
| `move: {id: {x, y, ease?}}` | the node glides to a new position; its connectors follow |
| `flow: {edge, label?, back?, reverse?, dur?}` | a token (label riding along) travels the connector; with `back`, a second token returns right away with that label and the start node reacts; `reverse: true` sends the token from the connector's end to its start (an answer that comes back later, after other steps). `path: [e1, e2, e3]` instead of `edge` = one token through a chain of connected connectors, each node reacting as it passes. A list of flows starts them `stagger` apart |
| `ease` | easing for this step's moves: `in_out_cubic` (default), `in_out_sine`, `out_cubic`, `out_quint`, `in_out_quint`, `out_expo`, `out_back`, `spring`, `linear` |

Nodes not shown by any step are there from the scene's start; connectors not drawn by any step draw once both of
their nodes are there. So a diagram that should simply build up only needs `show` steps.

### Continuing a diagram across scenes

`"continue": true` on a diagram scene that follows another diagram scene: shared ids stay exactly where they were,
in the state they ended in (no re-entrance); nodes whose position changed glide to their new place; new ids enter
on their steps; an unchanged `heading` stays put. The cut between the two scenes is invisible (no exit fade,
transition `none`, still camera). Use it to build one picture over several paragraphs instead of restarting it.

## Planning the motion (do this before writing JSON)

1. **Draw the final picture first**: which parts, how they connect, what travels. Then decide the order in which
   the narration introduces them. That order is your steps.
2. **One change per phrase.** Cue each step on the word that names its subject ("*sends it*" → the request token
   leaves). Something should change every ~2-5 s; nothing should be frozen for more than ~6 s.
3. **Show before you move.** A token travels only over a connector the viewer has already seen draw.
4. **Requests out, answers back.** Use `flow` with `back` for anything that asks and answers (a browser and a
   server, an agent and a tool). Use `path` when the same thing passes through several stages.
5. **Colours mean something**: accent = what is happening now, the success colour = done, the problem colour =
   failed. Do not light things up for decoration.
6. **Focus for comparisons and details**: `focus` the part being discussed, then `unfocus`. For "before / after",
   continue the diagram into the next scene and `move`, `label` or `hide` what changed.
7. **Keep it calm**: no camera push on diagrams (`"camera": "still"`), at most ~7 nodes per scene, at most ~3
   different kinds of change in one step. The renderer's motion is fixed and smooth; don't try to add effects.

### Patterns

| Teaching... | Pattern |
|---|---|
| a request and its answer | two nodes + one connector; `flow` with `label` and `back` (or, if something happens in between, a later `flow` with `reverse: true`) |
| a pipeline (data through stages) | `layout: row`; `show` stages in turn; one `flow` with `path` over all connectors |
| a loop (agent loop, water cycle) | `layout: cycle` + edges closing the loop; `activate` each stage on its word, `deactivate` the previous one |
| a hub (one service, many clients) | `layout: hub` with `center`; `flow` lists with `stagger` |
| a failure and its fix | `error` on the failing part, then (`continue`d scene) `label` it and `done` |
| two approaches | two `groups`; `focus` one, then the other |

## Checks

`oex validate` reports unknown ids (with the list of valid ones), broken `path` chains and nodes without positions.
`oex review` prompts on static or frozen diagrams, crowded steps and camera pushes over diagrams. Then look at the
preview: every step should land on its word, labels should be readable at a glance, and nothing should move that
the narration is not talking about.
