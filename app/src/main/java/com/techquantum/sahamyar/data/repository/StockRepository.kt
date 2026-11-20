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
    val analysis: StockAnalysisResponse?,
    val prices: StockPriceResponse?,
    val history: StockHistoryResponse?,
    val instrumentCategory: String?,
    val instrumentCategoryLabel: String?
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
        instrumentCategoryOverride: String? = null,
        instrumentCategoryLabelOverride: String? = null,
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
                val detail = api.getStockDetail(insCode).requireBody()
                val category = instrumentCategoryOverride
                    ?: detail.item?.instrument_category
                val categoryLabel = instrumentCategoryLabelOverride
                    ?: detail.item?.instrument_category_label
                val supportsStockTechnical =
                    category == "COMMON_STOCK" || category == "RIGHTS"

                val prices = async {
                    if (supportsStockTechnical) {
                        optionalRequest { api.getStockPrices(insCode).requireBody() }
                    } else null
                }
                val history = async {
                    if (supportsStockTechnical) {
                        optionalRequest {
                            api.getStockHistory(insCode, historyCount).requireBody()
                        }
                    } else null
                }
                val analysis = async {
                    if (supportsStockTechnical) {
                        optionalRequest {
                            api.getStockAnalysis(insCode, analysisCount).requireBody()
                        }
                    } else null
                }

                StockOverviewData(
                    detail = detail,
                    analysis = analysis.await(),
                    prices = prices.await(),
                    history = history.await(),
                    instrumentCategory = category,
                    instrumentCategoryLabel = categoryLabel
                )
            }
            Result.success(overview)
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    private suspend fun <T> optionalRequest(request: suspend () -> T): T? {
        return try {
            request()
        } catch (e: CancellationException) {
            throw e
        } catch (_: Exception) {
            null
        }
    }

    private fun <T : Any> Response<T>.requireBody(): T {
        if (!isSuccessful) {
            throw IllegalStateException("خطای سرور: ${code()}")
        }
        return body() ?: throw IllegalStateException("پاسخ سرور خالی است.")
    }
}
