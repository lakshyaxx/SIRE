/** Link only recognized source identities; prose brackets are never promoted to citations. */
export function citationLinks(text:string):string {
  return text.replace(/\[((?:(?:EV|SRC):[a-f\d]{64})|(?:[a-f\d]{24})|(?:[a-f\d]{32}(?::(?:schema|transcript|visual:\d+))?))\](?!\()/gi,
    (_,identifier:string)=>`[source ${identifier.slice(-8)}](#source=${encodeURIComponent(identifier)})`);
}
