package com.example.labelAI.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import com.example.labelAI.domain.User;
import com.example.labelAI.mapper.UserMapper;
import com.example.labelAI.service.UserService;
import com.example.labelAI.utils.JwtUtils;
import com.example.labelAI.utils.Result;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Service
public class UserServiceImpl implements UserService {
    @Autowired
    private UserMapper userMapper;
    @Autowired
    private JwtUtils jwtUtils;
    @Autowired
    private AuthenticationManager authenticationManager;
    @Autowired
    private RedisTemplate<String, Object> redisTemplate;
    @Autowired
    private PasswordEncoder passwordEncoder;

    @Override
    public List<User> getUsers() {
        return userMapper.selectList(null);
//return null;
    }

    @Override
    public Result login(String input,String password) {
//   进行用户认证


//  如果认证没通过，给出对应的提示


//  如果认证通过，使用userid生成一个jwt，jwt存入Result封装进行返回
//        String jwt = jwtUtils.createToken(user.getUserName());

//  把完整的用户信息存入redis userid作为key
//        return null;
        try {
            // 进行用户认证
            Authentication authentication = authenticationManager.authenticate(
                    new UsernamePasswordAuthenticationToken(input, password)
            );
            SecurityContextHolder.getContext().setAuthentication(authentication);
            Integer id = getUserId(input);
            // 如果认证通过，使用userid生成一个jwt，jwt存入Result封装进行返回
            String jwt = jwtUtils.createToken(input, id);

            // 把用户的ID和用户名存入redis
            Map<String, Object> userInfo = new HashMap<>();
            userInfo.put("id", id);
            userInfo.put("input", input);
            // 使用RedisTemplate的opsForHash方法
            redisTemplate.opsForHash().putAll("user:" + id, userInfo);
//            System.out.println("userInfo"+userInfo);
            // 创建一个Map对象，包含JWT
            Map<String, String> data = new HashMap<>();
            // 将jwt添加到Map中
            data.put("token", jwt);
            data.put("userid", id.toString());
            return Result.success(data);
        } catch (BadCredentialsException e) {
            // 如果认证没通过，给出对应的提示
            return Result.error(403, "用户名或密码错误");
        } catch (AuthenticationException e) {
            // 其他身份验证异常
            return Result.error(403, "身份验证失败");
        }
    }
public Integer getUserId(String input) {
    QueryWrapper<User> queryWrapper = new QueryWrapper<>();
    queryWrapper.eq("email", input).or().eq("user_name", input);
    User user = userMapper.selectOne(queryWrapper);
    return user != null ? user.getId().intValue() : null;


}

    /**
     * @DESCRIPTION: 退出登录
     * @param:
     * @return:
     */
    @Override
    public String logout(String token) {
        try {
            // 从JWT中获取用户名
            String input = jwtUtils.getEmailFromToken(token.substring(7));

            // 从Redis中删除用户信息
            Integer id = getUserId(input);
            redisTemplate.delete("user:" + id);
            // 返回成功信息
            return "用户已成功登出";
        } catch (Exception e) {
            // 如果出现异常，返回错误信息
            throw new RuntimeException("登出失败");
        }
    }

    /**
     * @DESCRIPTION: 注册用户
     * @param:
     * @return:
     */
    @Override
    public String registerUser(User user) {
        try {// 调用dao层，将用户信息插入数据库
            //默认是user，后续管理的时候调整
            user.setRole("user");
            // Encrypt the password
            String encryptedPassword = passwordEncoder.encode(user.getPassword());
            user.setPassword(encryptedPassword);
            userMapper.insertUser(user);
            return "注册用户成功";
        } catch (Exception e) {
            return "注册用户失败";
        }

    }
    /**
     *@DESCRIPTION: 检查邮箱是否已注册
     *
     * @param:
     * @return:
     */
    public String checkEmail(String email) {
        int count = userMapper.countByEmail(email);
        if (count > 0) {
            throw new RuntimeException("邮箱已经被注册");
        }
        return "邮箱可以使用";
    }
    /**
     *@DESCRIPTION: 检查用户名是否已注册
     *
     * @param:
     * @return:
     */
    public String checkName(String name) {
        int count = userMapper.countByName(name);
        if (count > 0) {
            throw new RuntimeException("用户名已经被注册");
        }
        return "用户名可以使用";
    }
}
