package com.techquantum.sahamyar.data.local.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import com.techquantum.sahamyar.data.local.entity.WatchlistEntity
import kotlinx.coroutines.flow.Flow

@Dao
interface WatchlistDao {
    @Query("SELECT * FROM watchlist_items WHERE listId = :listId ORDER BY addedAtMillis DESC")
    fun observeItems(listId: String = "default"): Flow<List<WatchlistEntity>>

    @Query("SELECT * FROM watchlist_items ORDER BY addedAtMillis DESC")
    fun observeAllItems(): Flow<List<WatchlistEntity>>

    @Query("SELECT EXISTS(SELECT 1 FROM watchlist_items WHERE insCode = :insCode)")
    suspend fun isTracked(insCode: String): Boolean

    @Insert(onConflict = OnConflictStrategy.IGNORE)
    suspend fun insert(item: WatchlistEntity): Long

    @Query("DELETE FROM watchlist_items WHERE id = :id")
    suspend fun deleteById(id: Long): Int

    @Query("DELETE FROM watchlist_items WHERE listId = :listId AND insCode = :insCode")
    suspend fun deleteBySymbol(listId: String, insCode: String): Int
}
