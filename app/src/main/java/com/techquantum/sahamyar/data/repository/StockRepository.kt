package com.techquantum.sahamyar.data.repository

import com.techquantum.sahamyar.data.remote.ApiClient
import com.techquantum.sahamyar.data.remote.model.StockAnalysisResponse
import com.techquantum.sahamyar.data.remote.model.StockDetailResponse
import com.techquantum.sahamyar.data.remote.model.StockHistoryResponse
import com.techquantum.sahamyar.data.remote.model.StockPriceResponse
import com.techquantum.sahamyar.data.remote.model.StockSearchResponse
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import retrofit2.Response

data class StockOverviewData(
    val detail: StockDetailResponse,
    val analysis: StockAnalysisResponse,
    val prices: StockPriceResponse,
    val history: StockHistoryResponse
)

class StockRepository {

    private val api = ApiClient.stockApi

    suspend fun searchStocks(query: String): Result<StockSearchResponse> {
        if (query.trim().length < 2) {
            return Result.failure(
                IllegalArgumentException("عبارت جستجو باید حداقل دو کاراکتر باشد.")
            )
        }

        return try {
            val response = api.searchStocks(query.trim())
            Result.success(response.requireBody())
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun getStockOverview(
        insCode: String,
        historyCount: Int = 365,
        analysisCount: Int = 365
    ): Result<StockOverviewData> {
        if (insCode.isBlank()) {
            return Result.failure(
                IllegalArgumentException("کد نماد معتبر نیست.")
            )
        }
        if (historyCount !in 1..365 || analysisCount !in 1..365) {
            return Result.failure(
                IllegalArgumentException("تعداد روزهای تاریخچه و تحلیل باید بین ۱ تا ۳۶۵ باشد.")
            )
        }

        return try {
            val overview = coroutineScope {
                val detail = async { api.getStockDetail(insCode).requireBody() }
                val prices = async { api.getStockPrices(insCode).requireBody() }
                val analysis = async {
                    api.getStockAnalysis(insCode, analysisCount).requireBody()
                }
                val history = async {
                    api.getStockHistory(insCode, historyCount).requireBody()
                }

                StockOverviewData(
                    detail = detail.await(),
                    analysis = analysis.await(),
                    prices = prices.await(),
                    history = history.await()
                )
            }
            Result.success(overview)
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    private fun <T : Any> Response<T>.requireBody(): T {
        if (!isSuccessful) {
            throw IllegalStateException("خطای سرور: ${code()}")
        }
        return body() ?: throw IllegalStateException("پاسخ سرور خالی است.")
    }
}
