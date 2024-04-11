package com.example.rmhospital.utils;

import java.time.LocalDateTime;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

@Data
@NoArgsConstructor
@AllArgsConstructor
public class Result<T> {
    private int code;
    private String message;
    private T data;
    private LocalDateTime timestamp;
    private boolean success;


    // 静态方法：成功结果
    public static <T> Result<T> success(T data) {
        return new Result<>(200, "Success", data, LocalDateTime.now(), true);
    }

    // 静态方法：失败结果
    public static <T> Result<T> error(int code ,String message) {
        return new Result<>(code, message, null, LocalDateTime.now(), false);
    }
}
