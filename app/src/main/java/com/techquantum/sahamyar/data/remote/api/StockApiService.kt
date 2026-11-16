package com.techquantum.sahamyar.data.remote.api

import com.techquantum.sahamyar.data.remote.model.StockAnalysisResponse
import com.techquantum.sahamyar.data.remote.model.StockDetailResponse
import com.techquantum.sahamyar.data.remote.model.StockHistoryResponse
import com.techquantum.sahamyar.data.remote.model.StockPriceResponse
import com.techquantum.sahamyar.data.remote.model.StockSearchResponse
import retrofit2.Response
import retrofit2.http.GET
import retrofit2.http.Path
import retrofit2.http.Query

interface StockApiService {

    @GET("api/v1/stocks/search")
    suspend fun searchStocks(
        @Query("q") query: String
    ): Response<StockSearchResponse>

    @GET("api/v1/stocks/{ins_code}")
    suspend fun getStockDetail(
        @Path("ins_code") insCode: String
    ): Response<StockDetailResponse>

    @GET("api/v1/stocks/{ins_code}/prices")
    suspend fun getStockPrices(
        @Path("ins_code") insCode: String
    ): Response<StockPriceResponse>

    @GET("api/v1/stocks/{ins_code}/analysis")
    suspend fun getStockAnalysis(
        @Path("ins_code") insCode: String,
        @Query("count") count: Int = 365
    ): Response<StockAnalysisResponse>

    @GET("api/v1/stocks/{ins_code}/history")
    suspend fun getStockHistory(
        @Path("ins_code") insCode: String,
        @Query("count") count: Int = 30
    ): Response<StockHistoryResponse>
}
