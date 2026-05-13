require('dotenv').config()
const neo4j = require('neo4j-driver')

const driver = neo4j.driver(
  process.env.NEO4J_URI,
  neo4j.auth.basic(
    process.env.NEO4J_USERNAME,
    process.env.NEO4J_PASSWORD
  )
)

async function test() {
  const session = driver.session()

  const result = await session.run(
    'RETURN "TasteGraph connected!" AS message'
  )

  console.log(result.records[0].get('message'))

  await session.close()
  await driver.close()
}

test()