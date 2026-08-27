import neo4j from "neo4j-driver"
import fs from "fs"
import path from "path"

const NEO4J_URI = process.env.NEO4J_URI || "neo4j+s://f4d8042a.databases.neo4j.io"
const NEO4J_USER = process.env.NEO4J_USERNAME || "neo4j"
const NEO4J_PASSWORD = process.env.NEO4J_PASSWORD || "QbeNaLH65LYDtboPkzU9iDO9N0XDyWh2wzLyCW47Lc4"
const NEO4J_DATABASE = process.env.NEO4J_DATABASE || "neo4j"

console.log("==================================================================")
console.log("  NEPALREFORMS TRACKER — NEO4J AURA GRAPH DEPLOYMENT ENGINE")
console.log("==================================================================")
console.log(`Connecting to Aura DB at: ${NEO4J_URI}`)

const driver = neo4j.driver(
  NEO4J_URI,
  neo4j.auth.basic(NEO4J_USER, NEO4J_PASSWORD),
  {
    maxConnectionLifetime: 3 * 60 * 60 * 1000,
    maxConnectionPoolSize: 50,
    connectionAcquisitionTimeout: 2 * 60 * 1000,
  }
)

async function deployGraph() {
  await driver.verifyConnectivity()
  console.log("✅ Verified secure connection to Neo4j Aura Instance.")

  const session = driver.session({ database: NEO4J_DATABASE })

  try {
    // -------------------------------------------------------------------------
    // 1. Install Constraints and Indexes
    // -------------------------------------------------------------------------
    console.log("\n[1/5] Installing Schema Constraints & Indexes...")
    const constraints = [
      "CREATE CONSTRAINT agenda_id_unique IF NOT EXISTS FOR (a:AgendaItem) REQUIRE a.id IS UNIQUE",
      "CREATE CONSTRAINT category_name_unique IF NOT EXISTS FOR (c:PolicyCategory) REQUIRE c.name IS UNIQUE",
      "CREATE CONSTRAINT party_code_unique IF NOT EXISTS FOR (p:PoliticalParty) REQUIRE p.code IS UNIQUE",
      "CREATE CONSTRAINT promise_id_unique IF NOT EXISTS FOR (prom:PoliticalPromise) REQUIRE prom.id IS UNIQUE",
      "CREATE CONSTRAINT province_name_unique IF NOT EXISTS FOR (pr:Province) REQUIRE pr.name IS UNIQUE",
      "CREATE CONSTRAINT fiscal_year_unique IF NOT EXISTS FOR (fy:FiscalYear) REQUIRE fy.year IS UNIQUE",
      "CREATE CONSTRAINT project_id_unique IF NOT EXISTS FOR (proj:Project) REQUIRE proj.id IS UNIQUE",
      "CREATE CONSTRAINT project_fingerprint_unique IF NOT EXISTS FOR (proj:Project) REQUIRE proj.fingerprint IS UNIQUE",
      "CREATE CONSTRAINT entity_name_unique IF NOT EXISTS FOR (e:ImplementingBody) REQUIRE e.name IS UNIQUE",
    ]

    for (const stmt of constraints) {
      await session.run(stmt)
    }
    console.log("   ✓ Constraints installed successfully.")

    // -------------------------------------------------------------------------
    // 2. Deploy Administrative & Territorial Nodes
    // -------------------------------------------------------------------------
    console.log("\n[2/5] Seeding Governance Levels, Provinces & Fiscal Years...")
    const provinces = [
      { id: "1", name: "Koshi Province", name_ne: "कोशी प्रदेश" },
      { id: "2", name: "Madhesh Province", name_ne: "मधेश प्रदेश" },
      { id: "3", name: "Bagmati Province", name_ne: "बागमती प्रदेश" },
      { id: "4", name: "Gandaki Province", name_ne: "गण्डकी प्रदेश" },
      { id: "5", name: "Lumbini Province", name_ne: "लुम्बिनी प्रदेश" },
      { id: "6", name: "Karnali Province", name_ne: "कर्णाली प्रदेश" },
      { id: "7", name: "Sudurpashchim Province", name_ne: "सुदूरपश्चिम प्रदेश" },
    ]

    for (const prov of provinces) {
      await session.run(
        `
        MERGE (pr:Province {name: $name})
        ON CREATE SET pr.id = $id, pr.name_ne = $name_ne, pr.created_at = datetime()
        SET pr.updated_at = datetime()
        `,
        prov
      )
    }

    const fiscalYears = ["2079/80", "2080/81", "2081/82", "2082/83"]
    for (const fy of fiscalYears) {
      await session.run(
        `
        MERGE (f:FiscalYear {year: $year})
        ON CREATE SET f.created_at = datetime()
        SET f.updated_at = datetime()
        `,
        { year: fy }
      )
    }

    // Federal Governance
    await session.run(`
      MERGE (g:GovernanceLevel {name: 'Federal'})
      ON CREATE SET g.jurisdiction = 'Nepal', g.house_seats = 275, g.created_at = datetime()
    `)
    console.log("   ✓ Seeded 7 Provinces, 4 Fiscal Years, and Federal Governance Level.")

    // -------------------------------------------------------------------------
    // 3. Ingest Core Reform Agendas Dossiers
    // -------------------------------------------------------------------------
    console.log("\n[3/5] Ingesting Core Reform Agendas from Dossiers...")
    const manifestoDir = path.resolve(__dirname, "../source/nepalrefors-manifesto")
    
    let files: string[] = []
    if (fs.existsSync(manifestoDir)) {
      files = fs.readdirSync(manifestoDir).filter(f => f.endsWith(".json"))
    }

    let agendaCount = 0
    for (const file of files) {
      const filePath = path.join(manifestoDir, file)
      const rawContent = fs.readFileSync(filePath, "utf-8")
      const raw = JSON.parse(rawContent)
      const agendaList = Array.isArray(raw.items) ? raw.items : (raw.id ? [raw] : [])

      for (const item of agendaList) {
        if (!item.id || !item.title) continue

      const agendaId = String(item.id)
      const categoryName = item.category || "General Governance"

      // 3.1 Create / Merge PolicyCategory
      await session.run(
        `
        MERGE (c:PolicyCategory {name: $categoryName})
        ON CREATE SET c.id = randomUUID(), c.created_at = datetime()
        `,
        { categoryName }
      )

      // 3.2 Create AgendaItem and link to category
      await session.run(
        `
        MERGE (a:AgendaItem {id: $agendaId})
        SET a.title = $title,
            a.description = $description,
            a.priority = $priority,
            a.category = $categoryName,
            a.timeline = $timeline,
            a.legalFoundation = $legalFoundation,
            a.status = 'Ingested',
            a.updated_at = datetime()
        WITH a
        MATCH (c:PolicyCategory {name: $categoryName})
        MERGE (a)-[:IN_CATEGORY]->(c)
        `,
        {
          agendaId,
          title: item.title,
          description: item.description || "",
          priority: item.priority || "High",
          categoryName,
          timeline: item.timeline || "Medium-term (1-3 years)",
          legalFoundation: item.legalFoundation || "",
        }
      )

      // 3.3 Create Problem Statement
      if (item.problem) {
        await session.run(
          `
          MATCH (a:AgendaItem {id: $agendaId})
          MERGE (p:ProblemStatement {agendaId: $agendaId})
          SET p.short = $short,
              p.long = $long,
              p.updated_at = datetime()
          MERGE (a)-[:HAS_PROBLEM_STATEMENT]->(p)
          `,
          {
            agendaId,
            short: item.problem.short || "",
            long: item.problem.long || "",
          }
        )
      }

      // 3.4 Create Solution Plan
      if (item.solution) {
        await session.run(
          `
          MATCH (a:AgendaItem {id: $agendaId})
          MERGE (s:SolutionPlan {agendaId: $agendaId})
          SET s.short = $short,
              s.phases = $phases,
              s.updated_at = datetime()
          MERGE (a)-[:HAS_SOLUTION_PLAN]->(s)
          `,
          {
            agendaId,
            short: Array.isArray(item.solution.short) ? item.solution.short : [],
            phases: JSON.stringify(item.solution.long?.phases || []),
          }
        )
      }

      // 3.5 Create Implementation Plan
      if (item.implementation) {
        await session.run(
          `
          MATCH (a:AgendaItem {id: $agendaId})
          MERGE (i:ImplementationPlan {agendaId: $agendaId})
          SET i.short = $short,
              i.phases = $phases,
              i.updated_at = datetime()
          MERGE (a)-[:HAS_IMPLEMENTATION_PLAN]->(i)
          `,
          {
            agendaId,
            short: Array.isArray(item.implementation.short) ? item.implementation.short : [],
            phases: JSON.stringify(item.implementation.long || []),
          }
        )
      }

      // 3.6 Create Real World Evidence
      if (item.realWorldEvidence) {
        await session.run(
          `
          MATCH (a:AgendaItem {id: $agendaId})
          MERGE (e:RealWorldEvidence {agendaId: $agendaId})
          SET e.short = $short,
              e.cases = $cases,
              e.updated_at = datetime()
          MERGE (a)-[:HAS_EVIDENCE]->(e)
          `,
          {
            agendaId,
            short: Array.isArray(item.realWorldEvidence.short) ? item.realWorldEvidence.short : [],
            cases: JSON.stringify(item.realWorldEvidence.long || []),
          }
        )
      }

      // 3.7 Performance Targets
      if (Array.isArray(item.performanceTargets) && item.performanceTargets.length > 0) {
        await session.run(
          `
          MATCH (a:AgendaItem {id: $agendaId})
          MERGE (t:PerformanceTarget {agendaId: $agendaId})
          SET t.targets = $targets,
              t.updated_at = datetime()
          MERGE (a)-[:HAS_TARGET]->(t)
          `,
          {
            agendaId,
            targets: item.performanceTargets,
          }
        )
      }

        agendaCount++
      }
    }
    console.log(`   ✓ Ingested ${agendaCount} Core Reform Agendas with full dossier substructures into Neo4j Aura.`)

    // -------------------------------------------------------------------------
    // 4. Ingest Political Parties & Manifesto Promises
    // -------------------------------------------------------------------------
    console.log("\n[4/5] Ingesting Political Parties & Manifesto Promises...")
    
    // Seed Major Political Parties
    const parties = [
      { code: "RSP", name: "Rastriya Swatantra Party", symbol: "Bell", manifesto: "Bacha Patra 2079" },
      { code: "NC", name: "Nepali Congress", symbol: "Tree", manifesto: "Sankalpa Patra 2079" },
      { code: "CPN-UML", name: "CPN (Unified Marxist-Leninist)", symbol: "Sun", manifesto: "Ghoshana Patra 2079" },
      { code: "CPN-MC", name: "CPN (Maoist Centre)", symbol: "Hammer & Sickle", manifesto: "Pratibaddhata 2079" },
    ]

    for (const party of parties) {
      await session.run(
        `
        MERGE (p:PoliticalParty {code: $code})
        ON CREATE SET p.name = $name, p.symbol = $symbol, p.manifesto_title = $manifesto, p.created_at = datetime()
        SET p.updated_at = datetime()
        `,
        party
      )
    }

    // Ingest RSP Pratipaakshya Promises
    const csvPath = path.resolve(__dirname, "../sources/RSPdocs/pratipaakshya.csv")
    let promiseCount = 0

    if (fs.existsSync(csvPath)) {
      const csvContent = fs.readFileSync(csvPath, "utf-8")
      const lines = csvContent.split("\n").filter(l => l.trim())
      
      for (let i = 1; i < lines.length; i++) {
        const line = lines[i].trim()
        if (!line) continue

        // Parse CSV line safely
        const parts = line.split(",")
        const category = parts[0]?.trim() || "Governance"
        const specificPromise = parts.slice(1, parts.length - 2).join(",").trim() || parts[1]?.trim()
        const targetDeadline = parts[parts.length - 2]?.trim() || "Unspecified"
        const responsibleEntity = parts[parts.length - 1]?.trim() || "Government"

        const promiseId = `RSP-PR-${String(i).padStart(3, "0")}`

        // Create Promise Node
        await session.run(
          `
          MERGE (prom:PoliticalPromise {id: $promiseId})
          SET prom.title = $specificPromise,
              prom.category = $category,
              prom.target_deadline = $targetDeadline,
              prom.responsible_entity = $responsibleEntity,
              prom.party_code = 'RSP',
              prom.status = 'Pledged',
              prom.source_document = 'pratipaakshya.csv',
              prom.updated_at = datetime()
          WITH prom
          MATCH (p:PoliticalParty {code: 'RSP'})
          MERGE (p)-[:COMMITTED_TO]->(prom)
          `,
          {
            promiseId,
            specificPromise,
            category,
            targetDeadline,
            responsibleEntity,
          }
        )

        // Semantic Category Link to AgendaItems
        await session.run(
          `
          MATCH (prom:PoliticalPromise {id: $promiseId})
          MATCH (a:AgendaItem)
          WHERE toLower(a.category) CONTAINS toLower($category) 
             OR toLower(a.title) CONTAINS toLower($category)
             OR toLower(prom.title) CONTAINS toLower(a.category)
          MERGE (prom)-[:ALIGNED_WITH]->(a)
          `,
          { promiseId, category }
        )

        // Implementing Body Link
        await session.run(
          `
          MATCH (prom:PoliticalPromise {id: $promiseId})
          MERGE (e:ImplementingBody {name: $responsibleEntity})
          ON CREATE SET e.id = randomUUID(), e.created_at = datetime()
          MERGE (prom)-[:ASSIGNED_TO]->(e)
          `,
          { promiseId, responsibleEntity }
        )

        promiseCount++
      }
    }
    console.log(`   ✓ Ingested ${promiseCount} Political Promises and linked them to Parties, AgendaItems & Implementing Bodies.`)

    // -------------------------------------------------------------------------
    // 5. Verification & Telemetry Summary
    // -------------------------------------------------------------------------
    console.log("\n[5/5] Running Graph Verification & Telemetry Query...")

    const nodeStatsQuery = `
      MATCH (n)
      RETURN labels(n)[0] AS label, count(n) AS count
      ORDER BY count DESC
    `
    const nodeStats = await session.run(nodeStatsQuery)

    const relStatsQuery = `
      MATCH ()-[r]->()
      RETURN type(r) AS relation_type, count(r) AS count
      ORDER BY count DESC
    `
    const relStats = await session.run(relStatsQuery)

    console.log("\n==================================================================")
    console.log("  NEO4J AURA GRAPH DEPLOYMENT REPORT ✨")
    console.log("==================================================================")
    console.log("📊 NODE METRICS:")
    for (const record of nodeStats.records) {
      const label = record.get("label") || "Unknown"
      const count = record.get("count").toNumber()
      console.log(`   • ${label.padEnd(28)} : ${count}`)
    }

    console.log("\n🔗 RELATIONSHIP METRICS:")
    for (const record of relStats.records) {
      const relType = record.get("relation_type") || "Unknown"
      const count = record.get("count").toNumber()
      console.log(`   • ${relType.padEnd(28)} : ${count}`)
    }

    const totalNodesRes = await session.run("MATCH (n) RETURN count(n) AS total")
    const totalRelsRes = await session.run("MATCH ()-[r]->() RETURN count(r) AS total")
    const totalNodes = totalNodesRes.records[0].get("total").toNumber()
    const totalRels = totalRelsRes.records[0].get("total").toNumber()

    console.log("------------------------------------------------------------------")
    console.log(`  TOTAL GRAPH NODES        : ${totalNodes}`)
    console.log(`  TOTAL GRAPH RELATIONSHIPS: ${totalRels}`)
    console.log("==================================================================")
    console.log("🚀 Neo4j Aura Graph is LIVE, healthy, and ready for queries!")
    console.log("==================================================================\n")

  } finally {
    await session.close()
    await driver.close()
  }
}

deployGraph().catch((err) => {
  console.error("❌ Fatal Error deploying graph to Neo4j Aura:", err)
  process.exit(1)
})
