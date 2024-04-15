package com.example.labelMark.vo.constant;

import com.fasterxml.jackson.databind.annotation.JsonSerialize;
import lombok.Data;

/**
 * @Description 统一API响应结果封装
 * @Author wh
 * @Date 2024/4/14
 */
@Data
// 非空返回
@JsonSerialize(include = JsonSerialize.Inclusion.NON_NULL)
public class Result {
    private int code;

    private String message = "success";

    private Object data;

    public Result setCode(StatusEnum resultCode) {
        this.code = resultCode.code;
        return this;
    }

    public Result setMessage(String message) {
        this.message = message;
        return this;
    }

    public Result setData(Object data) {
        this.data = data;
        return this;
    }
}
