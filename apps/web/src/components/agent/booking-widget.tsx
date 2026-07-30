"use client";

/**
 * Floating, button-driven booking assistant. Appears bottom-right once a
 * manager has approved one of the current candidate's applications for
 * interview (`GET /applications/me/awaiting-interview`, polled — nothing
 * pushes this client-side). Every step is a click: the transcript is chat-
 * shaped, but there is no free-text input anywhere in this component.
 *
 * Stateless against the backend by design (see the /interview/agent route):
 * this component is the only place a "conversation" is held, as the plain
 * `messages` array it echoes back on every click.
 */

import { CalendarCheck, Loader2, MessageCircle, X } from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";
import { toast } from "sonner";

import { BookInterviewDialog } from "@/components/calendar/book-interview-dialog";
import { ApiError, api } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import type { AgentButton, AgentMessage, AgentTurnOut, AwaitingInterviewItem } from "@/types/api";

const POLL_INTERVAL_MS = 30_000;

async function fetchAwaiting(): Promise<AwaitingInterviewItem[]> {
  try {
    return await api.get<AwaitingInterviewItem[]>("/applications/me/awaiting-interview");
  } catch {
    // A failed poll should never surface an error toast — it just tries
    // again next interval.
    return [];
  }
}

function postTurn(
  applicationId: string,
  history: AgentMessage[],
  selectedAction: string | null,
): Promise<AgentTurnOut> {
  return api.post<AgentTurnOut>(`/applications/${applicationId}/interview/agent`, {
    history,
    selected_action: selectedAction,
  });
}

function MessageBubble({ message }: { message: AgentMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "max-w-[85%] whitespace-pre-wrap rounded-2xl px-3 py-2 text-sm",
          isUser
            ? "bg-primary/25 text-foreground"
            : "border border-border bg-surface-2/60 text-foreground",
        )}
      >
        {message.content}
      </div>
    </div>
  );
}

export function BookingWidget() {
  const router = useRouter();
  const [awaiting, setAwaiting] = React.useState<AwaitingInterviewItem[]>([]);
  const [open, setOpen] = React.useState(false);
  const [active, setActive] = React.useState<AwaitingInterviewItem | null>(null);
  const [messages, setMessages] = React.useState<AgentMessage[]>([]);
  const [buttons, setButtons] = React.useState<AgentButton[]>([]);
  const [done, setDone] = React.useState(false);
  const [loading, setLoading] = React.useState(false);
  const scrollRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    let cancelled = false;
    const poll = () => {
      void fetchAwaiting().then((list) => {
        if (!cancelled) setAwaiting(list);
      });
    };
    poll();
    const interval = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  React.useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, buttons, loading]);

  function resetConversation() {
    setActive(null);
    setMessages([]);
    setButtons([]);
    setDone(false);
  }

  function closePanel() {
    setOpen(false);
    resetConversation();
  }

  async function startChat(item: AwaitingInterviewItem) {
    setActive(item);
    setMessages([]);
    setButtons([]);
    setDone(false);
    setLoading(true);
    try {
      const result = await postTurn(item.application_id, [], null);
      setMessages(result.history);
      setButtons(result.buttons);
      setDone(result.done);
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Could not start the booking assistant");
      setButtons([{ id: "retry", label: "Try again" }]);
    } finally {
      setLoading(false);
    }
  }

  async function clickButton(button: AgentButton) {
    if (!active || loading) return;
    const optimisticHistory: AgentMessage[] = [...messages, { role: "user", content: button.label }];
    setMessages(optimisticHistory);
    setButtons([]);
    setLoading(true);
    try {
      const result = await postTurn(active.application_id, optimisticHistory, button.id);
      setMessages(result.history);
      setButtons(result.buttons);
      setDone(result.done);
      if (result.done) {
        router.refresh();
        void fetchAwaiting().then(setAwaiting);
      }
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Something went wrong");
      setButtons([{ id: "retry", label: "Start over" }]);
    } finally {
      setLoading(false);
    }
  }

  function toggleOpen() {
    if (open) {
      closePanel();
      return;
    }
    setOpen(true);
    if (awaiting.length === 1) {
      void startChat(awaiting[0]);
    }
  }

  if (awaiting.length === 0 && !open) return null;

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-3">
      {open ? (
        <div className="panel-solid flex max-h-[70vh] w-[360px] max-w-[calc(100vw-2rem)] flex-col overflow-hidden rounded-2xl shadow-2xl">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <div>
              <p className="text-sm font-bold text-foreground">Interview booking assistant</p>
              <p className="text-xs text-subtle">{active?.job_title ?? "Pick a role to schedule"}</p>
            </div>
            <button
              type="button"
              onClick={closePanel}
              className="rounded-lg p-1.5 text-subtle transition-colors hover:bg-surface-2 hover:text-foreground"
            >
              <X className="size-4" />
              <span className="sr-only">Close</span>
            </button>
          </div>

          <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
            {!active ? (
              <div className="space-y-3">
                <p className="text-sm text-muted">
                  You have {awaiting.length} interviews to schedule. Which role would you like to book?
                </p>
                <div className="flex flex-col gap-2">
                  {awaiting.map((item) => (
                    <button
                      key={item.application_id}
                      type="button"
                      onClick={() => void startChat(item)}
                      className="rounded-xl border border-border bg-surface-2/40 px-3 py-2 text-left text-sm font-semibold text-foreground transition-colors hover:border-border-strong hover:bg-surface-2"
                    >
                      {item.job_title}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((message, index) => <MessageBubble key={index} message={message} />)
            )}

            {loading ? (
              <div className="flex justify-start">
                <div className="flex items-center gap-2 rounded-2xl border border-border bg-surface-2/60 px-3 py-2 text-sm text-muted">
                  <Loader2 className="size-3.5 animate-spin" />
                  Thinking…
                </div>
              </div>
            ) : null}

            {done ? (
              <div className="flex items-center gap-2 rounded-xl border border-success/30 bg-success/10 px-3 py-2 text-sm font-semibold text-success">
                <CalendarCheck className="size-4" />
                Interview booked
              </div>
            ) : null}
          </div>

          {active && !done && !loading && buttons.length > 0 ? (
            <div className="border-t border-border px-4 py-3">
              <div className="flex flex-wrap gap-2">
                {buttons.map((button) => (
                  <button
                    key={button.id}
                    type="button"
                    onClick={() => void clickButton(button)}
                    className="rounded-full border border-primary bg-primary/15 px-3 py-1.5 text-xs font-semibold text-foreground transition-colors hover:bg-primary/25"
                  >
                    {button.label}
                  </button>
                ))}
              </div>
              <BookInterviewDialog
                applicationId={active.application_id}
                jobTitle={active.job_title}
                trigger={
                  <button
                    type="button"
                    className="mt-2 text-xs text-subtle underline-offset-2 hover:text-muted hover:underline"
                  >
                    Having trouble? Use the classic picker instead
                  </button>
                }
              />
            </div>
          ) : null}
        </div>
      ) : null}

      <button
        type="button"
        onClick={toggleOpen}
        className="flex size-14 items-center justify-center rounded-full bg-gradient-to-r from-primary to-accent text-[#0b0614] shadow-lg shadow-primary/30 transition-all hover:brightness-110"
      >
        {open ? <X className="size-5" /> : <MessageCircle className="size-5" />}
        <span className="sr-only">{open ? "Close booking assistant" : "Open booking assistant"}</span>
      </button>
    </div>
  );
}
