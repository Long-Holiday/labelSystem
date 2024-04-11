package com.example.rmhospital.controller;

import com.example.rmhospital.domain.User;
import com.example.rmhospital.service.UserService;
import com.example.rmhospital.utils.Result;
import io.swagger.annotations.ApiOperation;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/user")
public class UserController {
    @Autowired
    private UserService userService;
    @PostMapping("/login")
    @ApiOperation(value = "用户登录", notes = "根据User对象登录用户")
    public Result<Map<String,String>> login(@RequestBody Map<String, String> requestBody) {
        // 调用userService的login方法进行登录，并返回结果
        String input = requestBody.get("input");
        String password = requestBody.get("password");
        return userService.login(input,password);
    }
    @PostMapping("/logout")
    @ApiOperation(value = "用户登出", notes = "用户登出并删除redis")
    public Result<String> logout(@RequestHeader(value="Authorization") String token) {
        try {
            // 调用UserService的logout方法进行登出，并返回结果
            String message = userService.logout(token);
            return Result.success(message);
        } catch (RuntimeException e) {
            // 如果出现异常，返回错误信息
            return Result.error(403, e.getMessage());
        }
    }
    @GetMapping("/getUsers")
    @ApiOperation(value = "获取用户列表", notes = "返回所有用户的列表")
    public Result<List<User>> getUsers() {

        try {
            List<User>users=userService.getUsers();

            return Result.success(users);
        } catch (Exception e) {
           return Result.error(400, "获取用户列表失败"+e.getMessage());
        }
    }

    @PostMapping("/checkEmail")
    @ApiOperation(value = "检查邮箱是否注册", notes = "接收一个邮箱并检查是否存在")
    public Result<String> checkEmail( @RequestBody Map<String, String> requestBody) {
        try {
            String email = requestBody.get("email");
            String msg = userService.checkEmail(email);
            return Result.success(msg);
        } catch (RuntimeException e) {
            // 如果出现异常，返回错误信息
            return Result.error(409, "邮箱已注册"+e.getMessage());
        }
    }
    @PostMapping("/checkName")
    @ApiOperation(value = "检查用户名是否重复", notes = "接收一个用户名并检查是否存在")
    public Result<String> checkName( @RequestBody Map<String, String> requestBody) {
        try {
            String name = requestBody.get("name");
            String msg = userService.checkEmail(name);
            return Result.success(msg);
        } catch (RuntimeException e) {
            // 如果出现异常，返回错误信息
            return Result.error(409, "用户名已注册"+e.getMessage());
        }
    }
    @PostMapping("/register")
    @ApiOperation(value = "注册用户", notes = "接收一个用户对象并进行注册")
    public Result<String> registerUser(@RequestBody User user) {
        try {
            String msg = userService.registerUser(user);
            return Result.success(msg);
        } catch (RuntimeException e) {
            // 如果出现异常，返回错误信息
            return Result.error(403, "注册用户失败"+e.getMessage());
        }
    }

}
