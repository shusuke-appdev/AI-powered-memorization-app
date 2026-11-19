import {useEffect, useState} from 'react';

export function useUnsaved(active: boolean) {
  useEffect(() => {
    if (!active) return;
    const before = (event: BeforeUnloadEvent) => {event.preventDefault(); event.returnValue = '';};
    window.addEventListener('beforeunload',before);
    return () => window.removeEventListener('beforeunload',before);
  },[active]);
}

export function confirmDiscard() {
  return window.confirm('未保存の内容があります。画面を切り替えますか？');
}

export function useDirtyScope() {
  const [dirty,setDirty] = useState(false);
  useUnsaved(dirty);
  return {dirty,setDirty};
}
