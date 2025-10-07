/**
 * TradingView Bundle Analyzer
 * Analyzes obfuscated/minified TradingView bundles for quotesSnapshot errors
 */

import fs from 'fs'

/**
 * Extract readable strings from obfuscated code
 */
function extractReadableStrings(code) {
  // Match quoted strings that might contain error messages
  const stringPattern = /["'`]([^"'`\n\r]{10,}?)["'`]/g
  const strings = []
  let match

  while ((match = stringPattern.exec(code)) !== null) {
    const str = match[1]
    // Filter for potentially meaningful strings
    if (
      str.includes('quote') ||
      str.includes('snapshot') ||
      str.includes('received') ||
      str.includes('error') ||
      str.includes('datafeed') ||
      str.includes('trading')
    ) {
      strings.push(str)
    }
  }

  return [...new Set(strings)] // Remove duplicates
}

/**
 * Find webpack module boundaries and extract module content
 */
function findWebpackModules(code) {
  // TradingView uses webpack, look for module pattern
  const modulePattern = /(\d+):\s*(?:function\s*)?(?:\([^)]*\)\s*)?=>?\s*{/g
  const modules = []
  let match

  while ((match = modulePattern.exec(code)) !== null && modules.length < 50) {
    const moduleId = match[1]
    const start = match.index

    // Try to find the end of this module (basic bracket matching)
    let braceCount = 0
    let end = start
    let inString = false
    let stringChar = ''

    for (let i = start; i < code.length && i < start + 10000; i++) {
      const char = code[i]
      const prevChar = i > 0 ? code[i - 1] : ''

      if (!inString && (char === '"' || char === "'")) {
        inString = true
        stringChar = char
      } else if (inString && char === stringChar && prevChar !== '\\') {
        inString = false
      }

      if (!inString) {
        if (char === '{') braceCount++
        if (char === '}') {
          braceCount--
          if (braceCount === 0) {
            end = i
            break
          }
        }
      }
    }

    const moduleContent = code.substring(start, end + 1)
    if (moduleContent.includes('quote') || moduleContent.includes('snapshot')) {
      modules.push({
        id: moduleId,
        content: moduleContent.substring(0, 1000) + '...', // Truncate for readability
      })
    }
  }

  return modules
}

/**
 * Search for specific patterns related to quotesSnapshot
 */
function findQuotesSnapshotPatterns(code) {
  const patterns = [
    {
      name: 'quotesSnapshot method calls',
      regex: /[a-zA-Z_$][a-zA-Z0-9_$]*\.quotesSnapshot\s*\(/g,
    },
    {
      name: 'quotesSnapshot property access',
      regex: /[a-zA-Z_$][a-zA-Z0-9_$]*\["?quotesSnapshot"?\]/g,
    },
    {
      name: 'quotesSnapshot error messages',
      regex: /["'].*quotesSnapshot.*not.*received.*["']/gi,
    },
    {
      name: 'quotesSnapshot timeout messages',
      regex: /["'].*quotesSnapshot.*timeout.*["']/gi,
    },
    {
      name: 'makeTimeLimited with quotesSnapshot',
      regex: /makeTimeLimited\([^,]*,\s*\d+,\s*["'].*quotesSnapshot.*["']\)/g,
    },
  ]

  const results = {}
  patterns.forEach((pattern) => {
    const matches = []
    let match
    while ((match = pattern.regex.exec(code)) !== null) {
      matches.push(match[0])
    }
    if (matches.length > 0) {
      results[pattern.name] = [...new Set(matches)]
    }
  })

  return results
}

/**
 * Extract error handling patterns
 */
function findErrorPatterns(code) {
  const errorPatterns = [
    /catch\s*\([^)]*\)\s*{[^}]*quote[^}]*}/g,
    /\.catch\([^)]*=>[^}]*quote[^}]*\)/g,
    /Promise\.reject\([^)]*quote[^)]*\)/g,
    /throw\s+new\s+Error\([^)]*quote[^)]*\)/g,
  ]

  const errors = []
  errorPatterns.forEach((pattern) => {
    let match
    while ((match = pattern.exec(code)) !== null) {
      errors.push(match[0].substring(0, 200) + '...')
    }
  })

  return errors
}

/**
 * Main analysis function
 */
export function analyzeBundle(filePath) {
  console.log('🔍 Analyzing TradingView bundle for quotesSnapshot issues...\n')

  if (!fs.existsSync(filePath)) {
    console.error(`❌ File not found: ${filePath}`)
    return
  }

  const code = fs.readFileSync(filePath, 'utf8')
  console.log(`📊 File size: ${(code.length / 1024 / 1024).toFixed(2)} MB`)

  // Extract readable strings
  console.log('\n📝 Extracting readable strings...')
  const strings = extractReadableStrings(code)
  const quoteRelatedStrings = strings.filter(
    (s) =>
      s.toLowerCase().includes('quote') ||
      s.toLowerCase().includes('snapshot') ||
      s.toLowerCase().includes('datafeed'),
  )

  if (quoteRelatedStrings.length > 0) {
    console.log('\n🎯 Quote-related strings found:')
    quoteRelatedStrings.slice(0, 20).forEach((str, i) => {
      console.log(`  ${i + 1}. "${str}"`)
    })
    if (quoteRelatedStrings.length > 20) {
      console.log(`  ... and ${quoteRelatedStrings.length - 20} more`)
    }
  }

  // Find quotesSnapshot patterns
  console.log('\n🔎 Searching for quotesSnapshot patterns...')
  const patterns = findQuotesSnapshotPatterns(code)
  Object.entries(patterns).forEach(([name, matches]) => {
    console.log(`\n  ${name}:`)
    matches.slice(0, 5).forEach((match) => {
      console.log(`    - ${match}`)
    })
    if (matches.length > 5) {
      console.log(`    ... and ${matches.length - 5} more`)
    }
  })

  // Find error patterns
  console.log('\n❌ Error handling patterns:')
  const errors = findErrorPatterns(code)
  if (errors.length > 0) {
    errors.slice(0, 5).forEach((error, i) => {
      console.log(`  ${i + 1}. ${error}`)
    })
  } else {
    console.log('  No error patterns found')
  }

  // Find webpack modules
  console.log('\n📦 Analyzing webpack modules...')
  const modules = findWebpackModules(code)
  if (modules.length > 0) {
    console.log(`  Found ${modules.length} modules with quote-related content:`)
    modules.slice(0, 3).forEach((module) => {
      console.log(`    Module ${module.id}: ${module.content.substring(0, 100)}...`)
    })
  }

  return {
    strings: quoteRelatedStrings,
    patterns,
    errors,
    modules,
  }
}

// CLI usage
if (import.meta.url === `file://${process.argv[1]}`) {
  const filePath = process.argv[2]
  if (!filePath) {
    console.log('Usage: node analyze-bundle.mjs <path-to-bundle-file>')
    process.exit(1)
  }

  const results = analyzeBundle(filePath)

  console.log('\n📋 Analysis Summary:')
  console.log(`  - ${results.strings.length} quote-related strings found`)
  console.log(`  - ${Object.keys(results.patterns).length} pattern types matched`)
  console.log(`  - ${results.errors.length} error handling patterns found`)
  console.log(`  - ${results.modules.length} relevant webpack modules found`)

  console.log('\n💡 Recommendations:')
  console.log('  1. Check your datafeed service implementation for quotesSnapshot method')
  console.log('  2. Ensure quotesSnapshot returns a Promise that resolves with quote data')
  console.log('  3. Verify the quote data format matches TradingView expectations')
  console.log('  4. Check for timeout issues (default timeout is typically 10 seconds)')
  console.log('  5. Look at browser console for more specific error details')
}
