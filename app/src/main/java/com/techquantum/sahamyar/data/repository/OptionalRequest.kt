package com.techquantum.sahamyar.data.repository

import com.techquantum.sahamyar.data.remote.api.TsetmcHttpException
import com.techquantum.sahamyar.data.remote.api.TsetmcInvalidResponseException
import kotlinx.coroutines.CancellationException
import java.io.IOException

internal suspend fun <T> executeOptionalRequest(
    request: suspend () -> T
): RequestResult<T> {
    return try {
        RequestResult(request(), RequestStatus.SUCCESS)
    } catch (e: CancellationException) {
        throw e
    } catch (e: IOException) {
        RequestResult(null, RequestStatus.NETWORK_ERROR, "ارتباط با سرور TSETMC برقرار نشد.")
    } catch (e: TsetmcHttpException) {
        RequestResult(null, RequestStatus.HTTP_ERROR, "درخواست HTTP به TSETMC ناموفق بود (HTTP ${e.statusCode}).")
    } catch (e: TsetmcInvalidResponseException) {
        RequestResult(null, RequestStatus.INVALID_DATA, "ساختار پاسخ TSETMC معتبر نیست.")
    } catch (e: Exception) {
        RequestResult(null, RequestStatus.INVALID_DATA, "پردازش اطلاعات دریافتی ناموفق بود.")
    }
}
