import {useEffect,useRef,useState} from 'react';
import {api,type InvestigationJob} from '../../lib/api';

/** Display durable actual progress while leaving the normal chat composer available. */
export function BackgroundInvestigation({conversationId,submitted,onFinished}:{conversationId:string|null;submitted:string|null;onFinished:(job:InvestigationJob)=>void}){
  const [job,setJob]=useState<InvestigationJob|null>(null);const [error,setError]=useState('');const finished=useRef('');const callback=useRef(onFinished);callback.current=onFinished;
  useEffect(()=>{setJob(null);setError('');if(!conversationId)return;let live=true;let timer:ReturnType<typeof setTimeout>|undefined;let sawActive=false;const abort=new AbortController();
    async function read(){try{const jobs=await api<InvestigationJob[]>(`/investigation-jobs?conversation_id=${encodeURIComponent(conversationId!)}`,undefined,undefined,abort.signal);if(!live)return;const current=jobs.find(item=>item.id===submitted)||jobs[0];setJob(current||null);if(current){if(['queued','running'].includes(current.status)){sawActive=true;timer=setTimeout(read,1000);}else if((sawActive||current.id===submitted)&&finished.current!==current.id){finished.current=current.id;callback.current(current);}}}catch(reason){if(live)setError((reason as Error).message);}}
    void read();return()=>{live=false;abort.abort();if(timer)clearTimeout(timer);};
  },[conversationId,submitted]);
  const active=job&&['queued','running'].includes(job.status);const step=job?.events.filter(event=>event.type==='tool').at(-1);
  const facts=job?.events.filter(event=>event.type==='delta'&&event.source==='validated_descriptive_measurement_statistics').map(event=>String(event.text)).join('\n');
  return <>{job&&<div className="stage" role="status">Investigation: {job.status}{step?` · ${String(step.tool)}: ${String(step.status)}`:''}{active&&<><span> · You can continue this conversation.</span><button type="button" onClick={()=>api<InvestigationJob>(`/investigation-jobs/${job.id}/cancel?conversation_id=${encodeURIComponent(job.conversation_id)}`,{}).then(setJob).catch(reason=>setError(reason.message))}>Stop investigation</button></>}{job.error&&<span role="alert">{job.error.message}</span>}</div>}{facts&&<details><summary>Verified intermediate source statistics</summary><pre style={{whiteSpace:'pre-wrap'}}>{facts}</pre><small>Exact uploaded-source statistics; physical association and cause remain unverified.</small></details>}{job?.events_trimmed?<small>Recent progress events only; the full saved result and tool trace remain available.</small>:null}{error&&<p role="alert" className="error">{error}</p>}</>;
}
