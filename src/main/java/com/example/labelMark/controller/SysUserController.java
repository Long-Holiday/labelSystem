package com.example.labelMark.controller;

import com.example.labelMark.domain.SysUser;
import com.example.labelMark.service.SysUserService;
import com.example.labelMark.utils.ResultGenerator;
import com.example.labelMark.vo.constant.Result;
import io.swagger.annotations.Api;
import io.swagger.annotations.ApiOperation;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestMethod;
import org.springframework.web.bind.annotation.RestController;

/**
 * <p>
 * 用户业务控制器
 * </p>
 *
 * @author wh
 * @since 2024-04-15
 */
@RestController
@RequestMapping("/user")
@Api(tags = "用户业务控制器")
public class SysUserController {

    @Autowired
    SysUserService sysUserService;

    @ApiOperation("创建用户")
    @RequestMapping(value = "/createUser", method = RequestMethod.POST)
    public Result createUser(@RequestBody SysUser user) {
        int isCreate = sysUserService.createUser(user);
        if (isCreate > 0) {
            return ResultGenerator.getSuccessResult();
        } else {
            return ResultGenerator.getFailResult("插入失败");
        }
    }

}
