export const meta = {
  name: 'research-swarm',
  description: 'Fan out 5 lenses (Consensus/Skeptic/Frontier/Historian/Experimental-Design) over a hypothesis, synthesize a neutral argument map',
  phases: [
    { title: 'Lenses', detail: '5 independent lenses, parallel, light web grounding' },
    { title: 'Synthesize', detail: 'merge into for/against + confidence tier + decisive experiment' },
    { title: 'Verify', detail: 'audit strongest claims vs evidence, calibrate the tier — or abstain' },
  ],
}

// args: { hypothesis: string, recall_context?: string }
// GOTCHA (claude-workflow-gotchas): args may arrive as a JSON STRING, not a parsed object.
let A = args
if (typeof A === 'string') { try { A = JSON.parse(A) } catch (e) { A = { hypothesis: A } } }
A = A || {}
const hypothesis = A.hypothesis || ''
const recall = A.recall_context || '(no prior vault context provided)'
if (!hypothesis) throw new Error('research-swarm: args.hypothesis is required')

const NEUTRALITY = `RULES (epistemic neutrality): Do NOT mock or dismiss the hypothesis. Consensus is NOT proof. Never use "scientists say" as a final argument. Separate facts from interpretation, data from conclusion, proven from assumed. Rate evidence honestly. You are building an argument map, not delivering a verdict. Do light, targeted web search to ground claims; cite reasoning. Stay token-aware.`

const CONTEXT = `HYPOTHESIS:\n${hypothesis}\n\nANTON'S PRIOR THINKING (from his Second Brain — build on it):\n${recall}`

const LENS_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    lens: { type: 'string' },
    stance_summary: { type: 'string', description: 'one paragraph: this lens\'s overall read' },
    points: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          claim: { type: 'string' },
          direction: { type: 'string', enum: ['for', 'against', 'context'] },
          evidence_quality: { type: 'string', enum: ['strong', 'moderate', 'weak', 'theoretical', 'none'] },
          reasoning: { type: 'string', description: 'why, with any source/citation' },
        },
        required: ['claim', 'direction', 'evidence_quality', 'reasoning'],
      },
    },
    confidence_note: { type: 'string' },
  },
  required: ['lens', 'stance_summary', 'points', 'confidence_note'],
}

const LENSES = [
  { key: 'Consensus', brief: 'Steelman the current mainstream/established view. What does well-replicated science or the market actually hold about this, and WHY. Be its best advocate — but mark where "consensus" is assumption vs proven.' },
  { key: 'Skeptic', brief: 'Strongest arguments AGAINST. Where does the idea break? Hidden assumptions, conservation laws / unit economics it must violate, known failure modes, the sharpest falsification test. Attack the idea, not the person.' },
  { key: 'Frontier', brief: 'Strongest arguments FOR. Steelman the believer: what would have to be true for this to work, adjacent emerging/anomalous evidence, why it is NOT obviously impossible, the most promising version of the idea.' },
  { key: 'Historian', brief: 'Precedents and base rates. Ideas in this domain once dismissed then vindicated, AND once hyped then debunked. What is the closest historical analog to THIS idea, and what did it teach? Give a calibrated base rate.' },
  { key: 'ExperimentalDesign', brief: 'How would we actually settle this? The cheapest DECISIVE experiment/measurement, what data to gather first, what result would confirm vs refute, and what a believer and a skeptic would both accept as a fair test.' },
]

phase('Lenses')
const lensResults = await parallel(
  LENSES.map((L) => () =>
    agent(
      `You are the ${L.key} lens of a research swarm analyzing a hypothesis.\n\n${L.brief}\n\n${NEUTRALITY}\n\n${CONTEXT}\n\nReturn your lens analysis.`,
      { label: `lens:${L.key}`, phase: 'Lenses', schema: LENS_SCHEMA }
    )
  )
).then((r) => r.filter(Boolean))

const ARG_ITEM = {
  type: 'object',
  additionalProperties: false,
  properties: {
    point: { type: 'string' },
    quality: { type: 'string', enum: ['strong', 'moderate', 'weak', 'theoretical'] },
    source_lens: { type: 'string' },
  },
  required: ['point', 'quality', 'source_lens'],
}

const MAP_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    hypothesis: { type: 'string' },
    confidence_tier: { type: 'string', enum: ['established', 'emerging', 'speculative', 'fringe', 'insufficient'] },
    confidence_rationale: { type: 'string' },
    for_arguments: { type: 'array', items: ARG_ITEM },
    against_arguments: { type: 'array', items: ARG_ITEM },
    historical_analogs: { type: 'array', items: { type: 'string' } },
    open_questions: { type: 'array', items: { type: 'string' } },
    decisive_experiment: {
      type: 'object',
      additionalProperties: false,
      properties: {
        description: { type: 'string' },
        why_decisive: { type: 'string' },
        rough_cost: { type: 'string' },
      },
      required: ['description', 'why_decisive'],
    },
    map_summary: { type: 'string', description: 'neutral 2-3 sentence read of the whole map — NO yes/no verdict' },
    verdict: { type: 'string', description: 'MUST be a no-verdict statement, e.g. "No verdict — see confidence tier and open questions"' },
  },
  required: ['hypothesis', 'confidence_tier', 'confidence_rationale', 'for_arguments', 'against_arguments', 'historical_analogs', 'open_questions', 'decisive_experiment', 'map_summary'],
}

phase('Synthesize')
const lensBlob = lensResults
  .map((l) => `### ${l.lens}\n${l.stance_summary}\nPoints:\n` + l.points.map((p) => `- [${p.direction}/${p.evidence_quality}] ${p.claim} — ${p.reasoning}`).join('\n') + `\nConfidence: ${l.confidence_note}`)
  .join('\n\n')

const argMap = await agent(
  `You are the synthesis node of a research swarm. Five lenses analyzed a hypothesis. Merge them into ONE neutral argument map.\n\n${NEUTRALITY}\nCRITICAL: Do NOT output a yes/no verdict. Output a confidence TIER with rationale, the strongest for/against arguments (dedup across lenses, keep each lens's best), historical analogs, open questions, and the cheapest decisive experiment. The 'verdict' field must explicitly say there is no verdict.\n\nABSTAIN LANE: the tier 'insufficient' is a FIRST-CLASS, honest answer — use it when the lenses did not surface enough real evidence to place the idea on the established→fringe axis. Abstaining ("data is too thin to judge") is better than a confident-looking tier with nothing under it. Reserve established/emerging for claims that actually have supporting evidence in the lens outputs.\n\nHYPOTHESIS:\n${hypothesis}\n\nLENS OUTPUTS:\n${lensBlob}`,
  { label: 'synthesize', phase: 'Synthesize', schema: MAP_SCHEMA }
)

// Verifier-Calibrator (DR gap #1+#5+#4): the synthesis tier is otherwise "numbers glued to a vibe".
// One agent audits the strongest claims against the evidence the lenses actually gave, then
// re-derives the tier from support density + cross-lens consistency — or abstains.
const VERIFY_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    claim_audits: {
      type: 'array',
      description: 'audit of the strongest for/against claims',
      items: {
        type: 'object',
        additionalProperties: false,
        properties: {
          claim: { type: 'string' },
          support: { type: 'string', enum: ['supported', 'partial', 'unsupported'] },
          note: { type: 'string', description: 'what backs it, or why it is unsupported' },
        },
        required: ['claim', 'support', 'note'],
      },
    },
    calibrated_tier: { type: 'string', enum: ['established', 'emerging', 'speculative', 'fringe', 'insufficient'] },
    tier_changed: { type: 'boolean' },
    calibration_rationale: { type: 'string', description: 'why this tier, grounded in support density + cross-lens consistency + audit outcomes' },
    flags: { type: 'array', items: { type: 'string' }, description: 'unsupported claims, single-lens-only points, weak-evidence warnings' },
  },
  required: ['claim_audits', 'calibrated_tier', 'tier_changed', 'calibration_rationale', 'flags'],
}

phase('Verify')
const argBlob = ['for_arguments', 'against_arguments']
  .map((k) => `${k}:\n` + (argMap[k] || []).map((a) => `- [${a.quality}] ${a.point} (from ${a.source_lens})`).join('\n'))
  .join('\n\n')

const calibration = await agent(
  `You are the Verifier-Calibrator of a research swarm — the acceptance function, NOT another opinion lens.\n\n${NEUTRALITY}\n\nTASK:\n1. AUDIT the strongest for/against claims below: is each actually SUPPORTED by the evidence the lenses gave, only PARTIAL, or UNSUPPORTED (asserted with no real backing)? Be a skeptic of the swarm itself.\n2. CALIBRATE the confidence tier from EVIDENCE, not vibe — driven by: how many audited claims are supported, whether multiple independent lenses agree (cross-lens consistency), and the evidence quality. A tier that rests on unsupported or single-lens claims must be LOWERED.\n3. ABSTAIN when warranted: output 'insufficient' if there is not enough supported evidence to place the idea on the established→fringe axis. Abstaining is a valid, honest result — do not invent confidence.\n4. FLAG every unsupported claim, single-lens-only point, and weak-evidence warning.\n\nThe synthesis proposed tier: "${argMap.confidence_tier}" — rationale: ${argMap.confidence_rationale}\n\nCLAIMS TO AUDIT:\n${argBlob}`,
  { label: 'verify-calibrate', phase: 'Verify', schema: VERIFY_SCHEMA }
)

// Calibrated tier becomes the map's tier; keep the synthesis tier for transparency.
if (calibration) {
  argMap.pre_calibration_tier = argMap.confidence_tier
  argMap.confidence_tier = calibration.calibrated_tier
  argMap.calibration = calibration
}

return { hypothesis, lenses: lensResults, map: argMap }
