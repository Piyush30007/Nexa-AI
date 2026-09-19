import assert from 'node:assert/strict'
import { api, setAuthTokenGetter } from './client.js'

async function runTests() {
  console.log('Running frontend client auth header tests...')

  let capturedUrl = null
  let capturedOptions = null

  // Mock global fetch
  globalThis.fetch = async (url, options) => {
    capturedUrl = url
    capturedOptions = options
    return {
      ok: true,
      status: 200,
      json: async () => ({ status: 'ok', mock: true }),
    }
  }

  // 1. Guest Request Test: No token getter (returns null)
  setAuthTokenGetter(async () => null)
  await api.chat('Hello guest query', 'conv-123')

  assert.equal(capturedUrl, 'http://localhost:8000/api/chat')
  assert.equal(capturedOptions.method, 'POST')
  assert.equal(capturedOptions.headers['Content-Type'], 'application/json')
  assert.equal(
    capturedOptions.headers['Authorization'],
    undefined,
    'Guest request must NOT have an Authorization header'
  )
  console.log('✅ TEST 1 PASSED: Guest request has no Authorization header.')

  // 2. Authenticated Request Test: Token getter returns Clerk JWT
  const mockClerkToken = 'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.mock_session_token'
  setAuthTokenGetter(async () => mockClerkToken)
  await api.chat('Authenticated policy query', 'conv-456')

  assert.equal(capturedUrl, 'http://localhost:8000/api/chat')
  assert.equal(
    capturedOptions.headers['Authorization'],
    `Bearer ${mockClerkToken}`,
    'Authenticated request must have Authorization: Bearer <Clerk session token>'
  )
  assert.equal(capturedOptions.headers['Content-Type'], 'application/json')
  console.log('✅ TEST 2 PASSED: Authenticated request includes Authorization: Bearer <token>.')

  // 3. Token Retrieval Failure Test: Token getter throws
  setAuthTokenGetter(async () => {
    throw new Error('Network timeout fetching session token')
  })

  let threw = false
  try {
    await api.chat('Failing token query')
  } catch (err) {
    threw = true
    assert.match(err.message, /Authentication token retrieval failed/)
    assert.match(err.message, /Network timeout fetching session token/)
  }
  assert.equal(threw, true, 'Request must fail clearly when token retrieval fails')
  console.log('✅ TEST 3 PASSED: Token retrieval failure fails clearly without sending request.')

  // Reset custom token getter
  setAuthTokenGetter(null)

  console.log('All frontend API client tests passed successfully!')
}

runTests().catch((err) => {
  console.error('Test failed:', err)
  process.exit(1)
})
