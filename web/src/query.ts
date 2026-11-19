import {useEffect, useState} from 'react';
import {api,message} from './api.ts';

export function useStudyQuery<T>(action: string, payload: object = {}, enabled = true, delay = 0) {
  const [revision, setRevision] = useState(0);
  const body = JSON.stringify(payload);
  const key = JSON.stringify([action,body,revision]);
  const [result,setResult] = useState<{key:string;data?:T;error?:string}>();
  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      void api<T>(action,JSON.parse(body),controller.signal).then(
        data => {if (!controller.signal.aborted) setResult({key,data});},
        error => {if (!controller.signal.aborted) setResult({key,error:message(error)});},
      );
    },delay);
    return () => {window.clearTimeout(timer);controller.abort();};
  },[action,body,enabled,key,delay]);

  return {
    data: enabled && result?.key === key ? result.data : undefined,
    error: enabled && result?.key === key ? result.error : undefined,
    loading: enabled && result?.key !== key,
    refresh: () => setRevision(value => value+1),
  };
}
