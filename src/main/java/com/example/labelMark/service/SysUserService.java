package com.example.labelMark.service;

import com.baomidou.mybatisplus.core.conditions.Wrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.baomidou.mybatisplus.extension.service.IService;
import com.example.labelMark.domain.Role;
import com.example.labelMark.domain.SysUser;

/**
 * <p>
 * 服务类
 * </p>
 *
 * @author wh
 * @since 2024-04-15
 */
public interface SysUserService extends IService<SysUser> {
    /**
     * 创建用户
     *
     * @param user
     * @return
     */
    int createUser(SysUser user);

    SysUser findByUsername(String username);

    SysUser findByUserId(Integer userId);

    boolean resetPassword(SysUser user);

    long getUsersCountByAdmin(int isAdmin);

    long getTotalCount();

    /**
     * 获取用户分页列表
     *
     * @param current
     * @param pageSize
     * @param userid
     * @param username
     * @return
     */
    Page<SysUser> getUsersPage(Integer current, Integer pageSize, Integer userid, String username, Integer isAdmin);

    boolean deleteUserById(Integer userid);

    boolean updateUser(Integer userid, String username, Integer isadmin);
}
