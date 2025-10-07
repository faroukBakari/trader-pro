#!/usr/bin/env node

import fs from 'fs'

// Simple JavaScript beautifier/formatter
function formatJS(code) {
  let formatted = code
  let indent = 0
  let result = ''
  let inString = false
  let stringChar = ''

  for (let i = 0; i < formatted.length; i++) {
    const char = formatted[i]
    const prevChar = i > 0 ? formatted[i - 1] : ''

    if (!inString && (char === '"' || char === "'")) {
      inString = true
      stringChar = char
    } else if (inString && char === stringChar && prevChar !== '\\') {
      inString = false
      stringChar = ''
    }

    if (!inString) {
      if (char === '{' || char === '[') {
        result += char + '\n' + '  '.repeat(++indent)
        continue
      } else if (char === '}' || char === ']') {
        result += '\n' + '  '.repeat(--indent) + char
        continue
      } else if (char === ';' && i < formatted.length - 1) {
        result += char + '\n' + '  '.repeat(indent)
        continue
      } else if (char === ',' && i < formatted.length - 1) {
        result += char + '\n' + '  '.repeat(indent)
        continue
      }
    }

    result += char
  }

  return result
}

// Extract strings that might be related to quotesSnapshot
function findQuotesSnapshotReferences(code) {
  const patterns = [
    /quotesSnapshot[^"'}]*["'}]/gi,
    /"quotesSnapshot[^"]*"/gi,
    /'quotesSnapshot[^']*'/gi,
    /quotesSnapshot\s*not\s*received/gi,
    /quotesSnapshot[^,;)}\]]*[,;)}\]]/gi,
  ]

  const matches = []
  patterns.forEach((pattern) => {
    const found = code.match(pattern)
    if (found) {
      matches.push(...found)
    }
  })

  return [...new Set(matches)] // Remove duplicates
}

// Extract function definitions that might be related
function findRelatedFunctions(code) {
  const patterns = [
    /function[^{]*quotes[^{]*{[^}]*}/gi,
    /[a-zA-Z_$][a-zA-Z0-9_$]*\s*:\s*function[^{]*{[^}]*quotes[^}]*}/gi,
    /[a-zA-Z_$][a-zA-Z0-9_$]*\s*=\s*function[^{]*{[^}]*quotes[^}]*}/gi,
  ]

  const matches = []
  patterns.forEach((pattern) => {
    const found = code.match(pattern)
    if (found) {
      matches.push(...found)
    }
  })

  return matches
}

// Main analysis function
function analyzeBundle(filePath) {
  console.log('Reading bundle file...')
  const code = fs.readFileSync(filePath, 'utf8')

  console.log(`File size: ${(code.length / 1024 / 1024).toFixed(2)} MB`)
  console.log('Searching for quotesSnapshot references...\n')

  const quotesRefs = findQuotesSnapshotReferences(code)
  if (quotesRefs.length > 0) {
    console.log('=== QUOTES SNAPSHOT REFERENCES ===')
    quotesRefs.forEach((ref, i) => {
      console.log(`${i + 1}. ${ref}`)
    })
    console.log('')
  }

  const functions = findRelatedFunctions(code)
  if (functions.length > 0) {
    console.log('=== RELATED FUNCTIONS ===')
    functions.forEach((func, i) => {
      console.log(`${i + 1}. ${func.substring(0, 200)}...`)
    })
    console.log('')
  }

  // Look for error messages
  const errorPatterns = [
    /['"](.*quotesSnapshot.*not.*received.*)['"]/gi,
    /['"](.*quotes.*not.*received.*)['"]/gi,
    /['"](.*snapshot.*not.*received.*)['"]/gi,
  ]

  console.log('=== ERROR MESSAGES ===')
  errorPatterns.forEach((pattern) => {
    const matches = code.match(pattern)
    if (matches) {
      matches.forEach((match) => {
        console.log(match)
      })
    }
  })

  // Extract webpack module structure
  console.log('\n=== WEBPACK MODULE ANALYSIS ===')
  const modulePattern = /(\d+):\s*[a-zA-Z_$][^,]*=>/g
  const modules = []
  let match
  while ((match = modulePattern.exec(code)) !== null && modules.length < 10) {
    modules.push(match[1])
  }
  console.log(`Found ${modules.length} webpack modules (showing first 10): ${modules.join(', ')}`)
}

// Create formatted version
function createFormattedVersion(inputPath, outputPath) {
  console.log('\nCreating formatted version...')
  const code = fs.readFileSync(inputPath, 'utf8')

  // Split into smaller chunks for better analysis
  const chunks = []
  const chunkSize = 50000 // 50KB chunks

  for (let i = 0; i < code.length; i += chunkSize) {
    chunks.push(code.substring(i, i + chunkSize))
  }

  const formattedChunks = chunks.map((chunk, index) => {
    console.log(`Formatting chunk ${index + 1}/${chunks.length}...`)
    return `// === CHUNK ${index + 1} ===\n${formatJS(chunk)}\n\n`
  })

  fs.writeFileSync(outputPath, formattedChunks.join(''))
  console.log(`Formatted version saved to: ${outputPath}`)
}

// Main execution
const inputFile = process.argv[2]
if (!inputFile) {
  console.log('Usage: node analyze-bundle.js <path-to-bundle-file>')
  process.exit(1)
}

if (!fs.existsSync(inputFile)) {
  console.log(`File not found: ${inputFile}`)
  process.exit(1)
}

analyzeBundle(inputFile)

const outputFile = inputFile.replace('.js', '-formatted.js')
createFormattedVersion(inputFile, outputFile)

console.log('\nAnalysis complete!')
console.log('\nTo further investigate the quotesSnapshot error:')
console.log('1. Look at the datafeed service implementation in your source code')
console.log('2. Check the TradingView API documentation for quotesSnapshot requirements')
console.log("3. The error likely comes from TradingView's internal validation")
console.log('4. Ensure your datafeed implements the quotesSnapshot method properly')
