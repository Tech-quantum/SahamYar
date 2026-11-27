package com.techquantum.sahamyar.data.repository

import com.techquantum.sahamyar.data.remote.api.TsetmcHttpException
import com.techquantum.sahamyar.data.remote.api.TsetmcInvalidResponseException
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertSame
import org.junit.Test
import java.io.IOException

class OptionalRequestTest {

    @Test
    fun successfulRequestReturnsData() = runBlocking {
        val result = executeOptionalRequest { "OK" }

        assertEquals("OK", result.data)
        assertEquals(RequestStatus.SUCCESS, result.status)
        assertNull(result.message)
    }

    @Test
    fun ioExceptionReturnsNetworkError() = runBlocking {
        val result = executeOptionalRequest<String> {
            throw IOException("Network unavailable")
        }

        assertNull(result.data)
        assertEquals(RequestStatus.NETWORK_ERROR, result.status)
        assertEquals("ارتباط با سرور TSETMC برقرار نشد.", result.message)
    }

    @Test
    fun httpExceptionReturnsHttpError() = runBlocking {
        val result = executeOptionalRequest<String> {
            throw TsetmcHttpException(503)
        }

        assertNull(result.data)
        assertEquals(RequestStatus.HTTP_ERROR, result.status)
        assertEquals("درخواست HTTP به TSETMC ناموفق بود (HTTP 503).", result.message)
    }

    @Test
    fun invalidResponseExceptionReturnsInvalidData() = runBlocking {
        val result = executeOptionalRequest<String> {
            throw TsetmcInvalidResponseException("Invalid payload")
        }

        assertNull(result.data)
        assertEquals(RequestStatus.INVALID_DATA, result.status)
        assertEquals("ساختار پاسخ TSETMC معتبر نیست.", result.message)
    }

    @Test
    fun genericExceptionReturnsInvalidData() = runBlocking {
        val result = executeOptionalRequest<String> {
            throw IllegalStateException("Unexpected error")
        }

        assertNull(result.data)
        assertEquals(RequestStatus.INVALID_DATA, result.status)
    }

    @Test
    fun cancellationExceptionIsRethrown() = runBlocking {
        val cancellation = CancellationException("Cancelled")

        try {
            executeOptionalRequest<String> {
                throw cancellation
            }
            throw AssertionError("CancellationException was swallowed")
        } catch (actual: CancellationException) {
            assertSame(cancellation, actual)
        }
    }
}
