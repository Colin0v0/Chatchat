import { useCallback, useMemo, useRef } from "react";

export function useLatestRequestGuard() {
  const sequenceRef = useRef(0);

  const begin = useCallback(() => {
    sequenceRef.current += 1;
    return sequenceRef.current;
  }, []);

  const isCurrent = useCallback((requestId: number) => sequenceRef.current === requestId, []);

  return useMemo(
    () => ({
      begin,
      isCurrent,
    }),
    [begin, isCurrent],
  );
}
