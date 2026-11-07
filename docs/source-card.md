# Source card

## Study input shapes

The operational study examined three maintenance-data shapes. The relational path was at work-order scale (order of magnitude: 10⁴ orders). Two daily-report paths contained repeated snapshots whose rows could not be assumed to represent distinct, completed interventions. These paths were analyzed separately because their units and completion evidence differ.

| Shape | Relevant field categories | Unit used in the study | Main quality condition |
|---|---|---|---|
| Relational work-order export | Order identifiers, technical-object references, dates, work type, narrative descriptions, reason, material items | Order or explicitly declared source unit | Text, item consumption, and technical-object registration vary by order |
| Daily PDF reports | Report date, asset reference, intervention notes, status text | Snapshot row and provisional event | Consecutive reports can describe the same open episode |
| Daily workbooks | Dated rows, activity notes, asset references, status fields | Snapshot row and provisional event | Repeated daily entries need temporal grouping and completion checks |

## Counting rules

- Declare **target × path × registration level × metric** before computing a figure.
- Keep order, physical record, event, snapshot row, term, and code pair as different units.
- Do not add denominators across paths.
- Record the eligible universe and any exclusions for each result.
- Treat a provisional event as a grouping hypothesis until episode boundaries are validated.

## Text and access

Visible operational text, site names, asset identifiers, and record-level derived artifacts were handled in restricted working areas. This public repository describes their schema and quality conditions. It contains no operational records or copy of a client catalog.

Illustrative examples are created for this publication and contain no operational records.
