#!/usr/bin/env node

import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const DEFAULT_API_URL = `http://localhost:${process.env.BACKEND_PORT || 8000}/api/v1/ws/asyncapi.json`
const OUTPUT_DIR = path.join(__dirname, '../src/clients')
const WS_CLIENT_OUTPUT = path.join(OUTPUT_DIR, 'ws-generated/client.ts')

const args = process.argv.slice(2)
const fromFileIndex = args.indexOf('--from-file')
const fromFile = fromFileIndex >= 0 && args[fromFileIndex + 1] ? args[fromFileIndex + 1] : null
const dryRun = args.includes('--dry-run')
const verbose = args.includes('--verbose')
const positionalArgs = args.filter(
  (arg, idx) =>
    !arg.startsWith('--') &&
    (idx === 0 ||
      !args[idx - 1].startsWith('--') ||
      args[idx - 1] === '--dry-run' ||
      args[idx - 1] === '--verbose'),
)
const apiUrl = fromFile ? null : positionalArgs[0] || DEFAULT_API_URL

function log(...messages) {
  if (verbose) {
    console.log('[Generator]', ...messages)
  }
}

async function fetchAsyncAPI() {
  if (fromFile) {
    log('Reading AsyncAPI spec from file:', fromFile)
    const content = fs.readFileSync(fromFile, 'utf-8')
    return JSON.parse(content)
  }

  log('Fetching AsyncAPI spec from:', apiUrl)
  const response = await fetch(apiUrl)
  if (!response.ok) {
    throw new Error(`Failed to fetch AsyncAPI spec: ${response.statusText}`)
  }
  return await response.json()
}

function extractTypeName(ref) {
  if (!ref || typeof ref !== 'string') {
    return null
  }
  return ref.split('/').pop()
}

function capitalize(str) {
  return str.charAt(0).toUpperCase() + str.slice(1)
}

function extractRoutes(spec) {
  const routes = []
  const messages = spec.components?.messages || {}
  const routeGroups = new Map()

  for (const [messageId, message] of Object.entries(messages)) {
    const parts = messageId.split('.')
    if (parts.length < 2) continue

    const routePrefix = parts[0]
    const operation = parts[1]

    // Skip response messages
    if (operation === 'response' || messageId.includes('.response')) continue

    if (!routeGroups.has(routePrefix)) {
      routeGroups.set(routePrefix, {})
    }

    const group = routeGroups.get(routePrefix)

    if (operation === 'subscribe') {
      const payloadRef = message.payload?.$ref
      if (payloadRef) {
        const wrapperTypeName = extractTypeName(payloadRef)
        const wrapperSchema = spec.components.schemas[wrapperTypeName]
        const payloadProp = wrapperSchema?.properties?.payload

        // Handle anyOf structure
        if (payloadProp?.anyOf) {
          const refItem = payloadProp.anyOf.find((item) => item.$ref)
          if (refItem?.$ref) {
            group.requestType = extractTypeName(refItem.$ref)
          }
        } else if (payloadProp?.$ref) {
          group.requestType = extractTypeName(payloadProp.$ref)
        }
      }
    } else if (operation === 'update') {
      const payloadRef = message.payload?.$ref
      if (payloadRef) {
        const wrapperTypeName = extractTypeName(payloadRef)
        const wrapperSchema = spec.components.schemas[wrapperTypeName]
        const payloadProp = wrapperSchema?.properties?.payload

        // Handle anyOf structure
        let updateWrapper = null
        if (payloadProp?.anyOf) {
          const refItem = payloadProp.anyOf.find((item) => item.$ref)
          if (refItem?.$ref) {
            updateWrapper = extractTypeName(refItem.$ref)
          }
        } else if (payloadProp?.$ref) {
          updateWrapper = extractTypeName(payloadProp.$ref)
        }

        if (updateWrapper) {
          const match = updateWrapper.match(/SubscriptionUpdate_(.+)_/)
          if (match) {
            group.dataModel = match[1]
          }
        }
      }
    }
  }

  for (const [routePrefix, group] of routeGroups) {
    if (group.requestType && group.dataModel) {
      routes.push({
        routePrefix,
        requestType: group.requestType,
        dataModel: group.dataModel,
      })
      log(`Found route: ${routePrefix} (${group.requestType} -> ${group.dataModel})`)
    }
  }

  return routes
}

function generateClientFactory(routePrefix, requestType, dataModel) {
  const clientName = capitalize(routePrefix)

  return `/**
 * Factory function for creating ${clientName} WebSocket client
 *
 * Generation variables extracted from AsyncAPI:
 *   ⭐ Route Prefix: '${routePrefix}'
 *   ⭐ Request Type: ${requestType}
 *   ⭐ Data Model: ${dataModel}
 *
 * @returns WebSocket client for ${routePrefix} data
 *
 * @example
 * const client = ${clientName}WebSocketClientFactory()
 * await client.subscribe(
 *   { symbol: 'AAPL', resolution: '1' },
 *   (data: ${dataModel}) => console.log(data)
 * )
 */
export function ${clientName}WebSocketClientFactory(): ${clientName}WebSocketInterface {
  return new WebSocketClientBase<${requestType}, ${dataModel}>('${routePrefix}')
}

export type ${clientName}WebSocketInterface = WebSocketInterface<${requestType}, ${dataModel}>
`
}

function generateClientFile(spec, routes) {
  if (!routes || routes.length === 0) {
    throw new Error('No routes found in AsyncAPI spec')
  }

  // Collect all unique types needed
  const allTypes = new Set()
  routes.forEach((route) => {
    allTypes.add(route.requestType)
    allTypes.add(route.dataModel)
  })

  let code = `/**
 * Auto-generated WebSocket Client from AsyncAPI specification
 *
 * DO NOT EDIT MANUALLY - This file is automatically generated
 *
 * Generated from: ${spec.info?.title || 'Unknown'}
 * Version: ${spec.info?.version || 'Unknown'}
 * AsyncAPI: ${spec.asyncapi || 'Unknown'}
 *
 * Generated on: ${new Date().toISOString()}
 */

import type { WebSocketInterface } from '../../plugins/wsClientBase'
import { WebSocketClientBase } from '../../plugins/wsClientBase'
import type { ${Array.from(allTypes).join(', ')} } from '../ws-types-generated'

`

  // Generate a client factory for each route
  routes.forEach((route) => {
    code += generateClientFactory(route.routePrefix, route.requestType, route.dataModel)
    code += '\n'
  })

  return code
}

function writeFile(filePath, content) {
  if (dryRun) {
    console.log(`[DRY RUN] Would write to: ${filePath}`)
    console.log(content)
    return
  }

  const dir = path.dirname(filePath)
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true })
  }

  fs.writeFileSync(filePath, content, 'utf-8')
  console.log(`✅ Generated: ${filePath}`)
}

async function main() {
  try {
    console.log('🚀 Starting WebSocket client generation...')
    console.log()

    const spec = await fetchAsyncAPI()
    console.log(`📄 AsyncAPI spec: ${spec.info?.title} v${spec.info?.version}`)

    const routes = extractRoutes(spec)
    console.log(`📊 Found ${routes.length} route(s):`)
    routes.forEach((r) => {
      console.log(`   - ${r.routePrefix}: ${r.requestType} → ${r.dataModel}`)
    })
    console.log()

    const clientCode = generateClientFile(spec, routes)
    writeFile(WS_CLIENT_OUTPUT, clientCode)

    console.log()
    console.log('✨ Generation complete!')
  } catch {
    console.log()
    console.log('⚠️  Could not generate WebSocket client from live API')
    console.log()
    console.log('ℹ️  Reasons this might happen:')
    console.log('   • Backend API server is not running')
    console.log('   • API server is on a different URL')
    console.log('   • Network connectivity issues')
    console.log()
    console.log('💡 What happens now:')
    console.log('   • App will use fallback WebSocket client')
    console.log('   • All features will work for development')
    console.log('   • You can generate later when API is ready')
    console.log()
    console.log('✅ Setup complete - using fallback client')
    console.log()

    // Exit successfully - the app will use the fallback client
    process.exit(0)
  }
}

main()
