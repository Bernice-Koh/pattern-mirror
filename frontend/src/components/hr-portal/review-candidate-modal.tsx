import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Modal } from '@/components/ui/modal'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  decideAddition,
  getProposalAudit,
  GrowthError,
} from '@/lib/growth-client'
import type {
  AgentArgument,
  GrowthAgentName,
  GrowthDecision,
  PendingAddition,
} from '@/lib/growth-contract'

const PENDING_ADDITIONS_KEY = ['growth', 'pending-additions']

const AGENT_LABELS: Record<GrowthAgentName, string> = {
  proposer: 'Proposer — argues for adding it',
  skeptic: 'Skeptic — argues against',
  categorizer: 'Categoriser — scope',
  citation: 'Citation — source found',
}

function reasoningOf(argument: AgentArgument): string {
  const { reasoning } = argument.output
  return typeof reasoning === 'string' ? reasoning : ''
}

interface ReviewCandidateModalProps {
  addition: PendingAddition
  onClose: () => void
}

/** The focused review of one queued phrase: the four agents' reasoning and the citation found,
 *  with approve / defer / reject. Reconstructs the agent arguments from the audit chain (#91) so
 *  HR decides a case, not a bare phrase (design spec §4). */
export function ReviewCandidateModal({
  addition,
  onClose,
}: Readonly<ReviewCandidateModalProps>) {
  const queryClient = useQueryClient()

  const audit = useQuery({
    queryKey: ['growth', 'audit', addition.proposal_id],
    queryFn: () => getProposalAudit(addition.proposal_id),
  })

  const decide = useMutation({
    mutationFn: (decision: GrowthDecision) =>
      decideAddition(addition.id, decision),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: PENDING_ADDITIONS_KEY })
      onClose()
    },
    onError: (error) => {
      // A 409 means another reviewer already decided it; refresh so it leaves the queue.
      if (error instanceof GrowthError && error.status === 409) {
        void queryClient.invalidateQueries({ queryKey: PENDING_ADDITIONS_KEY })
      }
    },
  })

  const citation = audit.data?.citation ?? addition.citation

  return (
    <Modal open onClose={onClose} title={`Review “${addition.phrase}”`}>
      <div className="flex items-center gap-3">
        <h2 className="font-serif text-subheading font-bold text-ink">
          {addition.phrase}
        </h2>
        <Badge tone="neutral" className="capitalize">
          {addition.proposed_category.replace('_', ' ')}
        </Badge>
      </div>

      <section className="mt-5">
        <h3 className="font-sans text-meta font-semibold tracking-wide text-ink-muted uppercase">
          What the review agents said
        </h3>
        {audit.isPending ? (
          <p className="mt-2 font-sans text-label text-ink-faint">Loading…</p>
        ) : audit.isError ? (
          <p className="mt-2 font-sans text-label text-ink-faint">
            The agent reasoning is unavailable.
          </p>
        ) : (
          <ul className="mt-2 flex flex-col gap-3">
            {audit.data.arguments.map((argument) => (
              <li key={argument.agent_name}>
                <p className="font-sans text-label font-semibold text-ink">
                  {AGENT_LABELS[argument.agent_name]}
                </p>
                <p className="font-sans text-label text-ink-muted">
                  {reasoningOf(argument)}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="mt-5">
        <h3 className="font-sans text-meta font-semibold tracking-wide text-ink-muted uppercase">
          Citation found
        </h3>
        {citation ? (
          <div className="mt-2 rounded-md border border-border p-3.5">
            <p className="font-sans text-label font-semibold text-ink">
              {citation.title}
              {citation.publication_year
                ? ` (${citation.publication_year})`
                : ''}
            </p>
            <p className="font-sans text-meta text-ink-faint">
              {citation.reference}
            </p>
            {citation.finding && (
              <p className="mt-1.5 font-sans text-label text-ink-muted">
                {citation.finding}
              </p>
            )}
          </div>
        ) : (
          <p className="mt-2 font-sans text-label text-ink-faint">
            No citation is attached to this phrase.
          </p>
        )}
      </section>

      {decide.isError && (
        <p className="mt-4 font-sans text-label text-red-primary">
          That decision could not be saved. The queue has been refreshed.
        </p>
      )}

      <div className="mt-6 flex items-center gap-3">
        <Button
          variant="primary"
          onClick={() => decide.mutate('approve')}
          disabled={decide.isPending}
        >
          Approve
        </Button>
        <Button
          variant="secondary"
          onClick={() => decide.mutate('defer')}
          disabled={decide.isPending}
        >
          Defer
        </Button>
        <Button
          variant="secondary"
          onClick={() => decide.mutate('reject')}
          disabled={decide.isPending}
        >
          Reject
        </Button>
        <button
          type="button"
          onClick={onClose}
          className="ml-auto font-sans text-label font-semibold text-ink-muted hover:text-ink"
        >
          Cancel
        </button>
      </div>
    </Modal>
  )
}
