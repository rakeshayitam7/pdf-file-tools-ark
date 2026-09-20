import {NextResponse} from 'next/server'

export const dynamic='force-dynamic'
export const revalidate=0

type Item={category:string;fact:string;source:string;url:string}

const fallback:Item[]=[
 {category:'SCIENCE',fact:'Light from the Sun takes about 8 minutes and 20 seconds to reach Earth.',source:'ARK Fact Library',url:''},
 {category:'SCIENCE',fact:'A day on Venus is longer than a Venus year.',source:'ARK Fact Library',url:''},
 {category:'SCIENCE',fact:'Water expands when it freezes, which makes ice less dense than liquid water.',source:'ARK Fact Library',url:''},
 {category:'SCIENCE',fact:'The human body contains trillions of cells working together.',source:'ARK Fact Library',url:''},
 {category:'SCIENCE',fact:'Sound travels faster through water than through air.',source:'ARK Fact Library',url:''},
 {category:'SPACE',fact:'Jupiter is the largest planet in our Solar System.',source:'ARK Fact Library',url:''},
 {category:'SPACE',fact:'The Moon is moving away from Earth by roughly 3.8 centimetres per year.',source:'ARK Fact Library',url:''},
 {category:'ENVIRONMENT',fact:'Forests store carbon in trees, roots and soils and help regulate the climate.',source:'ARK Fact Library',url:''},
 {category:'ENVIRONMENT',fact:'Oceans cover about 71 percent of Earth’s surface.',source:'ARK Fact Library',url:''},
 {category:'ENVIRONMENT',fact:'Mangrove ecosystems can reduce coastal erosion and provide habitat for many species.',source:'ARK Fact Library',url:''},
 {category:'ENVIRONMENT',fact:'Solar energy is produced by converting sunlight into electricity or heat.',source:'ARK Fact Library',url:''},
 {category:'HEALTH',fact:'Regular physical activity supports cardiovascular health, muscle strength and overall wellbeing.',source:'ARK Fact Library',url:''},
 {category:'HEALTH',fact:'Adequate sleep supports memory, learning and normal immune function.',source:'ARK Fact Library',url:''},
 {category:'HEALTH',fact:'Handwashing with soap is an effective way to reduce the spread of many infections.',source:'ARK Fact Library',url:''},
 {category:'HEALTH',fact:'Dietary fibre supports normal digestive function and is found in foods such as vegetables, fruits, beans and whole grains.',source:'ARK Fact Library',url:''},
 {category:'FOOD',fact:'Bananas are berries botanically, while strawberries are aggregate fruits.',source:'ARK Fact Library',url:''},
 {category:'FOOD',fact:'Fermentation is used to make foods such as yogurt, bread, kimchi and many cheeses.',source:'ARK Fact Library',url:''},
 {category:'FOOD',fact:'Whole grains contain the bran, germ and endosperm of the grain.',source:'ARK Fact Library',url:''},
 {category:'FOOD',fact:'Legumes such as lentils, chickpeas and beans are useful sources of plant protein and fibre.',source:'ARK Fact Library',url:''},
 {category:'TECHNOLOGY',fact:'QR codes can store information in two dimensions and can be read by cameras.',source:'ARK Fact Library',url:''},
 {category:'TECHNOLOGY',fact:'GPS receivers determine position by comparing timing signals from multiple satellites.',source:'ARK Fact Library',url:''},
 {category:'ENGINEERING',fact:'A sensor converts a physical quantity such as temperature, pressure or motion into a measurable signal.',source:'ARK Fact Library',url:''},
 {category:'ENGINEERING',fact:'LoRa is a low-power long-range radio technology commonly used for small IoT data packets.',source:'ARK Fact Library',url:''},
 {category:'GEOGRAPHY',fact:'Earth rotates once approximately every 24 hours, creating the cycle of day and night.',source:'ARK Fact Library',url:''},
 {category:'GEOGRAPHY',fact:'Mountains, rivers and coastlines continuously change through erosion, weathering and geological processes.',source:'ARK Fact Library',url:''},
 {category:'ANIMALS',fact:'Octopuses have three hearts and blue blood.',source:'ARK Fact Library',url:''},
 {category:'ANIMALS',fact:'Bees communicate important food-source information through movements known as the waggle dance.',source:'ARK Fact Library',url:''},
 {category:'MATERIALS',fact:'Copper is a very good conductor of electricity and is widely used in electrical wiring.',source:'ARK Fact Library',url:''},
 {category:'MATERIALS',fact:'Glass is an amorphous solid rather than a crystalline solid.',source:'ARK Fact Library',url:''},
]

const queries=[
  ['SCIENCE','science OR space OR astronomy OR research OR discovery'],
  ['ENVIRONMENT','environment OR climate OR biodiversity OR ocean OR conservation'],
  ['HEALTH','health OR medicine OR public health OR nutrition'],
  ['FOOD','food OR nutrition OR agriculture OR food science'],
] as const

async function getFactFacts(){
  const r=await fetch('https://factfacts.com/api.php?count=10',{cache:'no-store',headers:{accept:'application/json'}})
  if(!r.ok)throw new Error('FactFacts request failed')
  return r.json()
}

async function getGdelt(query:string){
  const url='https://api.gdeltproject.org/api/v2/doc/doc?query='+encodeURIComponent(query)+'&mode=artlist&format=json&maxrecords=8&sort=datedesc'
  const r=await fetch(url,{cache:'no-store',headers:{accept:'application/json'}})
  if(!r.ok)throw new Error('GDELT request failed')
  return r.json()
}

export async function GET(){
  const facts:Item[]=[...fallback]
  try{
    const data=await getFactFacts()
    const list=Array.isArray(data?.facts)?data.facts:[data?.fact].filter(Boolean)
    for(const x of list){
      if(x?.text)facts.unshift({category:String(x.category||'GENERAL').toUpperCase(),fact:String(x.text).trim(),source:'FactFacts open API',url:'https://factfacts.com/api/'})
    }
  }catch{}
  // Fresh headlines are optional; the useful static fact library remains available if news APIs fail.
  for(const [category,query] of queries){
    try{
      const data=await getGdelt(query)
      const articles=Array.isArray(data?.articles)?data.articles:[]
      const usable=articles.find((a:any)=>a?.title&&a?.url&&a?.domain)
      if(usable)facts.unshift({category,fact:String(usable.title).trim(),source:String(usable.domain),url:String(usable.url)})
    }catch{}
  }
  const unique=facts.filter((x,i,a)=>a.findIndex(y=>y.fact===x.fact)===i)
  return NextResponse.json({facts:unique.slice(0,40),updatedAt:new Date().toISOString(),source:'ARK open fact library with optional open APIs'})
}
