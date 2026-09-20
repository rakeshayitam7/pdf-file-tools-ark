import {NextResponse} from 'next/server'

export const dynamic='force-dynamic'
export const revalidate=0

type Item={category:string;fact:string;source:string;url:string}

const queries=[
  ['GEOPOLITICS','geopolitics OR diplomacy OR "international relations" OR "global affairs"'],
  ['SCIENCE','science OR space OR astronomy OR research OR discovery'],
  ['ENVIRONMENT','environment OR climate OR biodiversity OR ocean OR conservation'],
  ['HEALTH','health OR medicine OR "public health" OR nutrition'],
  ['FOOD','food OR nutrition OR agriculture OR "food science"'],
] as const

async function getGdelt(query:string){
  const url='https://api.gdeltproject.org/api/v2/doc/doc?query='+encodeURIComponent(query)+'&mode=artlist&format=json&maxrecords=8&sort=datedesc'
  const r=await fetch(url,{cache:'no-store',headers:{accept:'application/json'}})
  if(!r.ok) throw new Error('GDELT request failed')
  return r.json()
}

export async function GET(){
  const facts:Item[]=[]
  for(const [category,query] of queries){
    try{
      const data=await getGdelt(query)
      const articles=Array.isArray(data?.articles)?data.articles:[]
      const usable=articles.find((a:any)=>a?.title&&a?.url&&a?.domain)
      if(usable) facts.push({category,fact:String(usable.title).trim(),source:String(usable.domain),url:String(usable.url)})
    }catch{}
  }
  return NextResponse.json({facts,updatedAt:new Date().toISOString(),source:'GDELT open news data'})
}
