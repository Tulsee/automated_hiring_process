import { useCallback, useEffect, useRef, useState } from "react";

export interface AsyncState<T> {
  data: T | null;
  error: Error | null;
  loading: boolean;
  reload: () => void;
}

interface Result<T> {
  key: string;
  data: T | null;
  error: Error | null;
}

/**
 * Run an async fetch and track its state.
 *
 * `deps` identifies the request. Two details matter:
 *
 *   - `loading` is *derived* by comparing the current request key against the
 *     key of the last settled result, rather than being its own state. That
 *     keeps every `setState` inside an async callback instead of the effect
 *     body, so a re-fetch cannot cause a cascading render.
 *   - a result that arrives after the inputs changed, or after unmount, is
 *     discarded, so fast filter changes cannot leave a stale list on screen.
 */
export function useApi<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = [],
): AsyncState<T> {
  const [nonce, setNonce] = useState(0);
  const [result, setResult] = useState<Result<T> | null>(null);

  const key = JSON.stringify([deps, nonce]);

  // Initialised with the first fetcher, then refreshed in an effect so the
  // ref is never written during render.
  const fetcherRef = useRef(fetcher);

  useEffect(() => {
    fetcherRef.current = fetcher;
  });

  useEffect(() => {
    let active = true;

    fetcherRef
      .current()
      .then((data) => {
        if (active) setResult({ key, data, error: null });
      })
      .catch((caught: unknown) => {
        if (active) {
          setResult({
            key,
            data: null,
            error:
              caught instanceof Error ? caught : new Error(String(caught)),
          });
        }
      });

    return () => {
      active = false;
    };
  }, [key]);

  const reload = useCallback(() => setNonce((value) => value + 1), []);

  return {
    data: result?.data ?? null,
    error: result?.key === key ? result.error : null,
    loading: result?.key !== key,
    reload,
  };
}

/**
 * An action the user triggers (score, transcribe, apply), with its own
 * pending and error state so a button can disable itself while it runs.
 */
export function useAction<TArgs extends unknown[], TResult>(
  action: (...args: TArgs) => Promise<TResult>,
) {
  const [state, setState] = useState<{ pending: boolean; error: Error | null }>(
    { pending: false, error: null },
  );

  const actionRef = useRef(action);

  useEffect(() => {
    actionRef.current = action;
  });

  const run = useCallback(
    async (...args: TArgs): Promise<TResult | null> => {
      setState({ pending: true, error: null });

      try {
        const result = await actionRef.current(...args);

        setState({ pending: false, error: null });

        return result;
      } catch (caught: unknown) {
        setState({
          pending: false,
          error: caught instanceof Error ? caught : new Error(String(caught)),
        });

        return null;
      }
    },
    [],
  );

  return { run, pending: state.pending, error: state.error };
}
