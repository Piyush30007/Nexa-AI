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

  // 4. Authenticated getConversations Test
  setAuthTokenGetter(async () => mockClerkToken)
  await api.getConversations()

  assert.equal(capturedUrl, 'http://localhost:8000/api/conversations')
  assert.equal(capturedOptions.method, undefined) // default GET
  assert.equal(
    capturedOptions.headers['Authorization'],
    `Bearer ${mockClerkToken}`,
    'getConversations must include Authorization header'
  )
  console.log('✅ TEST 4 PASSED: getConversations includes Authorization: Bearer <token>.')

  // 5. Authenticated getConversationMessages Test
  await api.getConversationMessages('test-conv-uuid')

  assert.equal(capturedUrl, 'http://localhost:8000/api/conversations/test-conv-uuid/messages')
  assert.equal(capturedOptions.method, undefined) // default GET
  assert.equal(
    capturedOptions.headers['Authorization'],
    `Bearer ${mockClerkToken}`,
    'getConversationMessages must include Authorization header'
  )
  console.log('✅ TEST 5 PASSED: getConversationMessages includes Authorization: Bearer <token>.')

  // 6. Authenticated deleteConversation Test
  await api.deleteConversation('test-conv-uuid')

  assert.equal(capturedUrl, 'http://localhost:8000/api/conversations/test-conv-uuid')
  assert.equal(capturedOptions.method, 'DELETE')
  assert.equal(
    capturedOptions.headers['Authorization'],
    `Bearer ${mockClerkToken}`,
    'deleteConversation must include Authorization header with DELETE method'
  )
  console.log('✅ TEST 6 PASSED: deleteConversation sends DELETE with Authorization: Bearer <token>.')

  // 7. Guest getConversations Test (no token)
  setAuthTokenGetter(async () => null)
  await api.getConversations()

  assert.equal(capturedUrl, 'http://localhost:8000/api/conversations')
  assert.equal(
    capturedOptions.headers['Authorization'],
    undefined,
    'Guest call to getConversations must NOT have Authorization header'
  )
  console.log('✅ TEST 7 PASSED: Guest call does not include Authorization header.')

  // 8. Authenticated renameConversation Test
  setAuthTokenGetter(async () => mockClerkToken)
  await api.renameConversation('test-conv-uuid', 'Updated Policy Discussion')

  assert.equal(capturedUrl, 'http://localhost:8000/api/conversations/test-conv-uuid')
  assert.equal(capturedOptions.method, 'PATCH')
  assert.equal(
    capturedOptions.headers['Authorization'],
    `Bearer ${mockClerkToken}`,
    'renameConversation must include Authorization header'
  )
  assert.equal(
    capturedOptions.body,
    JSON.stringify({ title: 'Updated Policy Discussion' }),
    'renameConversation must send { title } body'
  )
  console.log('✅ TEST 8 PASSED: renameConversation sends PATCH with Authorization: Bearer <token> and title payload.')

  // Reset custom token getter
  setAuthTokenGetter(null)

  console.log('All frontend API client tests passed successfully!')
}

runTests().catch((err) => {
  console.error('Test failed:', err)
  process.exit(1)
})
