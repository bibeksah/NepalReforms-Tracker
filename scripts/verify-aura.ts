import neo4j from "neo4j-driver"

const NEO4J_URI = process.env.NEO4J_URI || "neo4j+s://f4d8042a.databases.neo4j.io"
const NEO4J_USER = process.env.NEO4J_USERNAME || "neo4j"
const NEO4J_PASSWORD = process.env.NEO4J_PASSWORD || "QbeNaLH65LYDtboPkzU9iDO9N0XDyWh2wzLyCW47Lc4"
const NEO4J_DATABASE = process.env.NEO4J_DATABASE || "neo4j"

const driver = neo4j.driver(NEO4J_URI, neo4j.auth.basic(NEO4J_USER, NEO4J_PASSWORD))

async function run() {
  const session = driver.session({ database: NEO4J_DATABASE })
  const res = await session.run(`
    MATCH (party:PoliticalParty)-[:COMMITTED_TO]->(prom:PoliticalPromise)-[:ALIGNED_WITH]->(agenda:AgendaItem)
    RETURN party.code AS party, prom.title AS promise, agenda.id AS agenda_id, agenda.title AS agenda_title
    LIMIT 5
  `)

  console.log("\n--- Sample Graph Relationships on Neo4j Aura ---")
  for (const r of res.records) {
    console.log(
      `• [${r.get("party")}] "${r.get("promise")}"\n  └──> Aligned with Agenda #${r.get("agenda_id")}: "${r.get("agenda_title")}"\n`
    )
  }

  await session.close()
  await driver.close()
}

run().catch(console.error)
