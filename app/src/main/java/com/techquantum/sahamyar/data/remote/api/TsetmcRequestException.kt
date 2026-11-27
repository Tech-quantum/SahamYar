package com.techquantum.sahamyar.data.remote.api

class TsetmcHttpException(
    val statusCode: Int
) : Exception("TSETMC HTTP error: $statusCode")

class TsetmcInvalidResponseException(
    message: String
) : Exception(message)
