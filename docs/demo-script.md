# Demo script (90 seconds)

Say these one at a time, out loud, waiting for each answer before the
next. Mic and headphones needed (see README Limits).

## Moment 1: KPI (0:00-0:20)

Say: **"What was net revenue last month?"**

Expect: a spoken number rounded for speech ("about 50.8 lakh rupees"),
naming the net_revenue definition. On screen: a KPI card with the same
number in full (Rs 50.81 lakh), the period, and an expandable Definition,
Evidence, and SQL.

## Moment 2: Breakdown (0:20-0:40)

Say: **"What were returns last week by city?"**

Expect: the agent names the top city and a rounded share of the total. On
screen: a bar chart by city, Mumbai standing out.

## Moment 3: Ambiguity (0:40-1:00)

Say: **"What was our revenue last month?"**

Expect: the agent does not guess - it asks one short question back ("did
you mean gross revenue or net revenue?"). On screen: a clarification card
naming both options as a reminder of the wording (not clickable - see
README Limits). Answer out loud, for example "net revenue," to continue.

## Moment 4: Why, with evidence (1:00-1:30)

Say: **"Why did returns go up for the Wireless Earbuds Pro this month?"**

Expect: the agent states the overall change, names Mumbai as the top
contributor and its share, and adds the correlation-not-cause caveat in
three sentences or fewer. On screen: a "why" card with the before/after
numbers, a contribution bar chart with Mumbai highlighted, and (since this
metric's volume also moved a lot) a note that part of the change is higher
order volume, not only a higher return rate.

## If something goes wrong live

- No sound at all: check the browser did not block microphone
  permission, and that the volume is not muted - the greeting plays
  immediately after clicking Start.
- Agent talks over itself or repeats: this is barge-in doing its job if
  you spoke over it; wait for it to finish once and re-ask.
- A number sounds wrong or garbled: stop and say so on camera rather than
  arguing with the agent - it should not happen (numbers come from
  `model_payload`, never computed by the model), but if it does, that is
  worth showing plainly.
