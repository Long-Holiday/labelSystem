package com.example.labelAI.utils;

import com.auth0.jwt.JWT;
import com.auth0.jwt.algorithms.Algorithm;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.util.Date;

/**
  * @description:用于处理Jwt令牌的工具类
  * @author: lf
  * @date:2023/12/3
 */
@Component
public class JwtUtils {

    //用于给Jwt令牌签名校验的秘钥
    @Value("${spring.security.jwt.key}")
    private String key;
    //令牌的过期时间，以小时为单位
    @Value("${spring.security.jwt.expire}")
    private int expire;
//    //为用户生成Jwt令牌的冷却时间，防止刷接口频繁登录生成令牌，以秒为单位
//    @Value("${spring.security.jwt.limit.base}")
//    private int limit_base;
//    //用户如果继续恶意刷令牌，更严厉的封禁时间
//    @Value("${spring.security.jwt.limit.upgrade}")
//    private int limit_upgrade;
//    //判定用户在冷却时间内，继续恶意刷令牌的次数
//    @Value("${spring.security.jwt.limit.frequency}")
//    private int limit_frequency;
    /**
     *@DESCRIPTION: 创建token
     *
     * @param:
     * @return:
     */

    public  String createToken(String subject,int userId) {
        Algorithm ALGORITHM = Algorithm.HMAC256(key);
        return JWT.create()
                .withClaim("name",subject)
                .withClaim("id",userId)
                .withExpiresAt(new Date(System.currentTimeMillis() + expire*3600_000))  // 1 hour
                .sign(ALGORITHM);
    }
    public  Integer getIdFromToken(String token) {
        Algorithm ALGORITHM = Algorithm.HMAC256(key);
        return JWT.require(ALGORITHM)
                .build()
                .verify(token)
                .getClaim("id")
                .asInt();
    }
    public  String getEmailFromToken(String token) {
        Algorithm ALGORITHM = Algorithm.HMAC256(key);
        return JWT.require(ALGORITHM)
                .build()
                .verify(token)
                .getClaim("input")
                .asString();
    }

    /**
     * 校验并转换请求头中的Token令牌
     * @param headerToken 请求头中的Token
     * @return 转换后的令牌
     */
    public String convertToken(String headerToken){
        if(headerToken == null || !headerToken.startsWith("Bearer "))
            return null;
        return headerToken.substring(7);
    }

}
